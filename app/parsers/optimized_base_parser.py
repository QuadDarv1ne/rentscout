"""
Улучшенный базовый парсер с connection pooling и оптимизациями.
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import httpx
from app.utils.enhanced_http import EnhancedHTTPClient
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

from app.models.schemas import PropertyCreate
from app.utils.performance import track_performance, PerformanceMonitor


@dataclass
class ParserConfig:
    """Конфигурация парсера."""
    name: str
    base_url: str
    timeout: int = 30
    max_retries: int = 3
    rate_limit: int = 10  # requests per second
    max_concurrent: int = 5
    cache_ttl: int = 300  # seconds


class OptimizedBaseParser(ABC):
    """
    Оптимизированный базовый класс для всех парсеров.
    
    Особенности:
    - Connection pooling через httpx.AsyncClient
    - Автоматический retry с экспоненциальной задержкой
    - Rate limiting для соблюдения лимитов API
    - Конкурентная обработка с ограничением
    - Встроенный мониторинг производительности
    - Кеширование результатов
    """
    
    def __init__(self, config: ParserConfig):
        """
        Инициализация парсера.
        
        Args:
            config: Конфигурация парсера
        """
        self.config = config
        self.name = config.name
        self._client: Optional[EnhancedHTTPClient] = None
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._rate_limiter = asyncio.Semaphore(config.rate_limit)
        self._last_request_time = 0.0
        self._cache: Dict[str, tuple[datetime, Any]] = {}
        self._perf_monitor = PerformanceMonitor()
        
    async def __aenter__(self):
        """Контекстный менеджер - вход."""
        await self._initialize_client()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход."""
        await self._close_client()
        
    async def _initialize_client(self):
        """Инициализация улучшенного HTTP клиента."""
        if self._client is None:
            self._client = EnhancedHTTPClient()
            # Создаём внутреннюю сессию
            await self._client.create_session()
            
    async def _close_client(self):
        """Закрытие HTTP клиента."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            
    async def _rate_limit_wait(self):
        """Ожидание для соблюдения rate limit."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        min_interval = 1.0 / self.config.rate_limit
        
        if time_since_last < min_interval:
            await asyncio.sleep(min_interval - time_since_last)
            
        self._last_request_time = asyncio.get_event_loop().time()
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError))
    )
    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> httpx.Response:
        """
        Выполнение HTTP запроса с retry и rate limiting.
        
        Args:
            method: HTTP метод (GET, POST, etc.)
            url: URL для запроса
            **kwargs: Дополнительные параметры для httpx
            
        Returns:
            HTTP Response
        """
        async with self._semaphore:
            await self._rate_limit_wait()
            
            if self._client is None:
                await self._initialize_client()

            # Используем методы enhanced клиента
            method_upper = method.upper()
            if method_upper == "GET":
                response = await self._client.get(url, **kwargs)
            elif method_upper == "POST":
                response = await self._client.post(url, **kwargs)
            else:
                # Для других методов, пробуем напрямую через внутреннюю сессию
                response = await self._client.session.request(method_upper, url, **kwargs)
            response.raise_for_status()
            return response
            
    def _get_cache_key(self, location: str, params: Dict[str, Any]) -> str:
        """Генерация ключа кеша."""
        params_str = "_".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{self.name}:{location}:{params_str}"
        
    def _get_from_cache(self, cache_key: str) -> Optional[List[PropertyCreate]]:
        """Получение данных из кеша."""
        if cache_key in self._cache:
            timestamp, data = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.config.cache_ttl):
                return data
            else:
                del self._cache[cache_key]
        return None
        
    def _save_to_cache(self, cache_key: str, data: List[PropertyCreate]):
        """Сохранение данных в кеш."""
        self._cache[cache_key] = (datetime.now(), data)
        
        # Очистка старых записей из кеша
        now = datetime.now()
        expired_keys = [
            key for key, (timestamp, _) in self._cache.items()
            if now - timestamp >= timedelta(seconds=self.config.cache_ttl)
        ]
        for key in expired_keys:
            del self._cache[key]
            
    @track_performance(operation_name="parse")
    async def parse(
        self, 
        location: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> List[PropertyCreate]:
        """
        Парсинг данных с кешированием и мониторингом.
        
        Args:
            location: Город или местоположение
            params: Дополнительные параметры поиска
            
        Returns:
            Список объектов PropertyCreate
        """
        params = params or {}
        
        # Проверка кеша
        cache_key = self._get_cache_key(location, params)
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            return cached_data
            
        # Валидация параметров
        if not await self.validate_params(params):
            raise ValueError(f"Invalid parameters for {self.name}")
            
        # Предобработка
        processed_params = await self.preprocess_params(params)
        
        # Основной парсинг
        results = await self._parse_impl(location, processed_params)
        
        # Постобработка
        processed_results = await self.postprocess_results(results)
        
        # Сохранение в кеш
        self._save_to_cache(cache_key, processed_results)
        
        return processed_results
        
    @abstractmethod
    async def _parse_impl(
        self, 
        location: str, 
        params: Dict[str, Any]
    ) -> List[PropertyCreate]:
        """
        Реализация парсинга (должна быть переопределена в подклассах).
        
        Args:
            location: Город или местоположение
            params: Обработанные параметры поиска
            
        Returns:
            Список объектов PropertyCreate
        """
        pass
        
    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Валидация параметров (может быть переопределена).
        
        Args:
            params: Параметры для валидации
            
        Returns:
            True если параметры валидны
        """
        return True
        
    async def preprocess_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Предобработка параметров (может быть переопределена).
        
        Args:
            params: Исходные параметры
            
        Returns:
            Обработанные параметры
        """
        return params
        
    async def postprocess_results(
        self, 
        results: List[PropertyCreate]
    ) -> List[PropertyCreate]:
        """
        Постобработка результатов (может быть переопределена).
        
        Args:
            results: Исходные результаты
            
        Returns:
            Обработанные результаты
        """
        return results
        
    async def batch_parse(
        self, 
        locations: List[str], 
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[PropertyCreate]]:
        """
        Пакетный парсинг нескольких локаций с конкурентностью.
        
        Args:
            locations: Список локаций
            params: Параметры поиска
            
        Returns:
            Словарь {location: results}
        """
        tasks = [self.parse(location, params) for location in locations]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            location: result if not isinstance(result, Exception) else []
            for location, result in zip(locations, results)
        }
        
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики парсера."""
        return {
            "name": self.name,
            "cache_size": len(self._cache),
            "performance": self._perf_monitor.get_summary()
        }
