"""
Менеджер пула HTTP-соединений для оптимизированной производительности парсеров.
Переиспользует соединения и реализует лучшие практики для асинхронных HTTP клиентов.
"""
import asyncio
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.utils.logger import logger


class HTTPClientPool:
    """
    Singleton менеджер пула HTTP клиентов.
    Предоставляет оптимизированный пулинг соединений для парсеров.
    """
    
    _instance: Optional['HTTPClientPool'] = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.clients: Dict[str, httpx.AsyncClient] = {}
            self._initialized = True
            logger.info("HTTPClientPool initialized")
    
    async def get_client(
        self,
        name: str = "default",
        **kwargs
    ) -> httpx.AsyncClient:
        """
        Получить или создать HTTP клиент с пулом соединений.
        
        Args:
            name: Идентификатор клиента
            **kwargs: Дополнительные параметры httpx.AsyncClient
        
        Returns:
            Настроенный асинхронный HTTP клиент
        """
        async with self._lock:
            if name not in self.clients:
                # Default limits optimized for web scraping
                default_limits = httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=100,
                    keepalive_expiry=30.0
                )
                
                # Default timeout
                default_timeout = httpx.Timeout(
                    connect=10.0,
                    read=30.0,
                    write=10.0,
                    pool=5.0
                )
                
                # Merge with custom parameters
                limits = kwargs.pop('limits', default_limits)
                timeout = kwargs.pop('timeout', default_timeout)
                
                # Create client with best practices
                self.clients[name] = httpx.AsyncClient(
                    limits=limits,
                    timeout=timeout,
                    http2=True,  # Enable HTTP/2
                    follow_redirects=True,
                    verify=True,
                    **kwargs
                )
                
                logger.info(f"Created HTTP client '{name}' with connection pool")
            
            return self.clients[name]
    
    async def close_client(self, name: str) -> None:
        """Закрыть конкретный клиент."""
        async with self._lock:
            if name in self.clients:
                await self.clients[name].aclose()
                del self.clients[name]
                logger.info(f"Closed HTTP client '{name}'")
    
    async def close_all(self) -> None:
        """Закрыть все клиенты."""
        async with self._lock:
            for name, client in self.clients.items():
                await client.aclose()
                logger.info(f"Closed HTTP client '{name}'")
            self.clients.clear()


# Global pool instance
http_pool = HTTPClientPool()


class OptimizedHTTPClient:
    """
    Оптимизированный HTTP клиент для парсеров с логикой повторных попыток и лучшими практиками.
    """
    
    def __init__(self, name: str = "parser", user_agent: Optional[str] = None):
        self.name = name
        self.user_agent = user_agent or self._get_default_user_agent()
        self._client: Optional[httpx.AsyncClient] = None
    
    @staticmethod
    def _get_default_user_agent() -> str:
        """Получить строку user agent по умолчанию."""
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    
    async def __aenter__(self):
        """Вход в контекстный менеджер."""
        self._client = await http_pool.get_client(
            name=self.name,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера - не закрываем клиент, сохраняем пул активным."""
        pass
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Оптимизированный GET запрос с логикой повторных попыток.
        
        Args:
            url: Целевой URL
            params: Параметры запроса
            **kwargs: Дополнительные параметры httpx запроса
        
        Returns:
            HTTP ответ
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        try:
            response = await self._client.get(url, params=params, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} for {url}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> httpx.Response:
        """
        Оптимизированный POST запрос с логикой повторных попыток.
        
        Args:
            url: Целевой URL
            data: Данные формы
            json: JSON данные
            **kwargs: Дополнительные параметры httpx запроса
        
        Returns:
            HTTP ответ
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        try:
            response = await self._client.post(url, data=data, json=json, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error {e.response.status_code} for {url}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error for {url}: {e}")
            raise


# Convenience function for quick usage
@asynccontextmanager
async def get_http_client(name: str = "default"):
    """
    Контекстный менеджер для получения HTTP клиента.
    
    Пример:
        async with get_http_client("avito") as client:
            response = await client.get("https://avito.ru")
    """
    client = OptimizedHTTPClient(name=name)
    async with client:
        yield client
