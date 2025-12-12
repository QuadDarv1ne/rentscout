"""
Улучшенный HTTP клиент с поддержкой прокси, случайных заголовков и задержек
"""
import asyncio
import random
from typing import Optional, Dict, Any
import httpx
from app.core.config import settings
from app.utils.headers import get_random_headers
from app.utils.proxy import proxy_manager
from app.utils.logger import logger


class EnhancedHTTPClient:
    """
    Продвинутый HTTP клиент для обхода защиты сайтов
    
    Особенности:
    - Случайные User-Agent и заголовки
    - Поддержка прокси с ротацией
    - Автоматические задержки между запросами
    - Обработка ошибок и повторные попытки
    """
    
    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self.last_request_time: float = 0
    
    async def __aenter__(self):
        await self.create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def create_session(self):
        """Создает новую HTTP сессию с настройками"""
        proxies = None
        
        if settings.PROXY_ENABLED:
            proxy = proxy_manager.get_random_proxy()
            if proxy:
                proxies = proxy.to_httpx_proxy()
                logger.info(f"Using proxy: {proxy.host}:{proxy.port}")
        
        self.session = httpx.AsyncClient(
            proxies=proxies,
            timeout=httpx.Timeout(settings.REQUEST_TIMEOUT),
            follow_redirects=False,  # Не следуем редиректам автоматически
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            verify=False,  # Отключаем проверку SSL (только для разработки!)
        )
    
    async def _add_random_delay(self):
        """Добавляет случайную задержку между запросами"""
        import time
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < settings.MIN_REQUEST_DELAY:
            delay = random.uniform(
                settings.MIN_REQUEST_DELAY - time_since_last_request,
                settings.MAX_REQUEST_DELAY
            )
            logger.debug(f"Adding delay: {delay:.2f}s")
            await asyncio.sleep(delay)
        
        self.last_request_time = time.time()
    
    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        use_random_headers: bool = True,
        **kwargs
    ) -> httpx.Response:
        """
        Выполняет GET запрос с защитой от блокировки
        
        Args:
            url: URL для запроса
            headers: Дополнительные заголовки
            params: Query параметры
            use_random_headers: Использовать случайные заголовки
            **kwargs: Дополнительные аргументы для httpx
            
        Returns:
            HTTP ответ
        """
        if not self.session:
            await self.create_session()
        
        # Добавляем задержку
        await self._add_random_delay()
        
        # Генерируем заголовки
        if use_random_headers and settings.USE_RANDOM_HEADERS:
            request_headers = get_random_headers()
            if headers:
                request_headers.update(headers)
        else:
            request_headers = headers or {}
        
        logger.debug(f"GET {url}")
        
        try:
            response = await self.session.get(
                url,
                headers=request_headers,
                params=params,
                **kwargs
            )
            return response
        except httpx.ProxyError as e:
            logger.error(f"Proxy error: {e}")
            # Помечаем прокси как неработающий
            if settings.PROXY_ENABLED and proxy_manager.get_random_proxy():
                proxy = proxy_manager.get_random_proxy()
                if proxy:
                    proxy_manager.mark_as_failed(proxy)
            raise
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise
    
    async def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        use_random_headers: bool = True,
        **kwargs
    ) -> httpx.Response:
        """
        Выполняет POST запрос с защитой от блокировки
        
        Args:
            url: URL для запроса
            headers: Дополнительные заголовки
            data: Form data
            json: JSON данные
            use_random_headers: Использовать случайные заголовки
            **kwargs: Дополнительные аргументы для httpx
            
        Returns:
            HTTP ответ
        """
        if not self.session:
            await self.create_session()
        
        # Добавляем задержку
        await self._add_random_delay()
        
        # Генерируем заголовки
        if use_random_headers and settings.USE_RANDOM_HEADERS:
            request_headers = get_random_headers()
            if headers:
                request_headers.update(headers)
        else:
            request_headers = headers or {}
        
        logger.debug(f"POST {url}")
        
        try:
            response = await self.session.post(
                url,
                headers=request_headers,
                data=data,
                json=json,
                **kwargs
            )
            return response
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise
    
    async def close(self):
        """Закрывает HTTP сессию"""
        if self.session:
            await self.session.aclose()
            self.session = None
