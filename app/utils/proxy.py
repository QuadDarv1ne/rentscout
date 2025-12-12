"""
Менеджер прокси-серверов для парсинга
"""
import random
from typing import Optional, List, Dict
from dataclasses import dataclass
import httpx
from app.utils.logger import logger


@dataclass
class ProxyConfig:
    """Конфигурация прокси"""
    protocol: str  # http, https, socks5
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    
    def to_url(self) -> str:
        """Конвертирует в URL формат"""
        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"
    
    def to_httpx_proxy(self) -> Dict[str, str]:
        """Конвертирует в формат httpx"""
        proxy_url = self.to_url()
        return {
            "http://": proxy_url,
            "https://": proxy_url,
        }


class ProxyManager:
    """Менеджер для работы с прокси-серверами"""
    
    def __init__(self):
        self.proxies: List[ProxyConfig] = []
        self.failed_proxies: set = set()
        self._load_proxies()
    
    def _load_proxies(self):
        """
        Загружает список прокси из конфигурации или файла
        
        Примеры бесплатных источников прокси:
        - https://free-proxy-list.net/
        - https://www.proxy-list.download/
        - https://www.sslproxies.org/
        """
        # TODO: Загрузить из файла или переменных окружения
        # Пример:
        # self.proxies.append(ProxyConfig(
        #     protocol="http",
        #     host="proxy.example.com",
        #     port=8080,
        #     username="user",
        #     password="pass"
        # ))
        pass
    
    def get_random_proxy(self) -> Optional[ProxyConfig]:
        """Возвращает случайный рабочий прокси"""
        available_proxies = [p for p in self.proxies if p.to_url() not in self.failed_proxies]
        
        if not available_proxies:
            logger.warning("No available proxies")
            return None
        
        return random.choice(available_proxies)
    
    def mark_as_failed(self, proxy: ProxyConfig):
        """Помечает прокси как неработающий"""
        self.failed_proxies.add(proxy.to_url())
        logger.warning(f"Proxy marked as failed: {proxy.host}:{proxy.port}")
    
    async def test_proxy(self, proxy: ProxyConfig, test_url: str = "https://httpbin.org/ip") -> bool:
        """
        Тестирует работоспособность прокси
        
        Args:
            proxy: Конфигурация прокси
            test_url: URL для тестирования
            
        Returns:
            True если прокси работает
        """
        try:
            async with httpx.AsyncClient(proxies=proxy.to_httpx_proxy(), timeout=10.0) as client:
                response = await client.get(test_url)
                if response.status_code == 200:
                    logger.info(f"Proxy {proxy.host}:{proxy.port} is working")
                    return True
        except Exception as e:
            logger.error(f"Proxy test failed for {proxy.host}:{proxy.port}: {e}")
        
        return False
    
    def add_proxy(self, proxy: ProxyConfig):
        """Добавляет прокси в список"""
        self.proxies.append(proxy)
        logger.info(f"Added proxy: {proxy.host}:{proxy.port}")
    
    def clear_failed(self):
        """Очищает список неработающих прокси"""
        self.failed_proxies.clear()
        logger.info("Cleared failed proxies list")


# Глобальный экземпляр
proxy_manager = ProxyManager()
