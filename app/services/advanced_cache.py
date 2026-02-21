"""Расширенное кеширование с поддержкой парсеров, cache warming и метрик."""

import asyncio
import hashlib
import json
import pickle
import logging
import zlib
import fnmatch
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Dict, List, Set
from functools import wraps

import redis.asyncio as redis

from app.core.config import settings
from app.models.schemas import PropertyCreate
from app.utils.metrics import metrics_collector

logger = logging.getLogger(__name__)


class InMemoryAsyncRedis:
    """Простейшая in-memory реализация Redis API для тестов и fallback с поддержкой TTL."""

    def __init__(self):
        # store: key -> (value, expires_at)
        self.store: Dict[str, Any] = {}
        self.sets: Dict[str, Set[str]] = {}

    async def ping(self):
        return True

    async def get(self, key: str):
        item = self.store.get(key)
        if item is None:
            return None

        value, expires_at = item
        if expires_at and time.time() > expires_at:
            await self.delete(key)
            return None
        return value

    async def setex(self, key: str, expire: int, value: Any):
        expires_at = time.time() + expire if expire else None
        self.store[key] = (value, expires_at)
        return True

    async def delete(self, *keys: str):
        deleted = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                deleted += 1
        return deleted

    async def sadd(self, key: str, *values: str):
        if key not in self.sets:
            self.sets[key] = set()
        before = len(self.sets[key])
        self.sets[key].update(values)
        return len(self.sets[key]) - before

    async def smembers(self, key: str):
        return self.sets.get(key, set())

    async def expire(self, key: str, expire: int):
        if key in self.store:
            value, _ = self.store[key]
            self.store[key] = (value, time.time() + expire)
        return True

    async def scan(self, cursor: int = 0, match: Optional[str] = None, count: int = 100):
        # Очистка истекших ключей
        now = time.time()
        expired_keys = [k for k, (_, exp) in self.store.items() if exp and now > exp]
        for key in expired_keys:
            await self.delete(key)

        keys = list(self.store.keys())
        if match:
            keys = fnmatch.filter(keys, match)
        return 0, keys[:count]

    async def info(self, section: Optional[str] = None):
        return {}

    async def dbsize(self):
        # Учитываем только не истекшие ключи
        await self.scan()
        return len(self.store)

    async def close(self):
        return True


class AdvancedCacheManager:
    """Расширенный менеджер кеша с метриками и cache warming."""

    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        
        # Метрики кеша
        self.hits = 0
        self.misses = 0
        self.errors = 0
        
        # Popular cities для cache warming
        self.popular_cities: Set[str] = {
            "Москва", "Санкт-Петербург", "Новосибирск", 
            "Екатеринбург", "Казань", "Нижний Новгород"
        }
        
        # Cache warming priorities
        self.warming_priorities: Dict[str, int] = {
            "Москва": 10,
            "Санкт-Петербург": 9,
            "Новосибирск": 5,
            "Екатеринбург": 5,
            "Казань": 4,
            "Нижний Новгород": 4,
        }

    async def connect(self):
        """Подключение к Redis с повторными попытками и connection pooling."""
        max_retries = 1  # Быстрая проверка в dev
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=False,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    max_connections=50,  # Connection pool size
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                await self.redis_client.ping()
                logger.info(f"✅ Successfully connected to Redis at {self.redis_url}")
                return True
            except Exception as e:
                # В dev режиме просто молча отключаем Redis
                logger.debug(f"Redis unavailable (attempt {attempt + 1}/{max_retries}): {type(e).__name__}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.info("ℹ️  Redis unavailable - using in-memory cache fallback (for dev/tests)")
                    self.redis_client = InMemoryAsyncRedis()
                    return True

    async def disconnect(self):
        """Отключение от Redis."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")

    async def get(self, key: str) -> Optional[Any]:
        """Получение значения из кеша с метриками."""
        if not self.redis_client:
            return None

        try:
            value = await self.redis_client.get(key)
            if value:
                self.hits += 1
                metrics_collector.record_cache_hit()
                logger.debug(f"Cache HIT: {key[:50]}... (hit rate: {self.get_hit_rate():.2%})")
                # Decompress if compressed
                if value.startswith(b'COMPRESSED:'):
                    compressed_data = value[11:]  # Remove prefix
                    decompressed_data = zlib.decompress(compressed_data)
                    return pickle.loads(decompressed_data)
                else:
                    return pickle.loads(value)
            else:
                self.misses += 1
                metrics_collector.record_cache_miss()
                logger.debug(f"Cache MISS: {key[:50]}... (hit rate: {self.get_hit_rate():.2%})")
                return None
        except Exception as e:
            self.errors += 1
            metrics_collector.record_cache_error()
            logger.error(f"Error getting value from cache: {e}")
            return None

    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: int = settings.CACHE_TTL,
        tags: Optional[List[str]] = None,
        compress: bool = True
    ) -> bool:
        """Сохранение значения в кеше с тегами."""
        if not self.redis_client:
            return False

        try:
            serialized_value = pickle.dumps(value)
            
            # Compress large values to save memory
            if compress and len(serialized_value) > 1024:  # Compress if > 1KB
                compressed_value = zlib.compress(serialized_value)
                final_value = b'COMPRESSED:' + compressed_value
                logger.debug(f"Compressed cache value from {len(serialized_value)} to {len(final_value)} bytes")
            else:
                final_value = serialized_value
            
            # Устанавливаем основное значение
            result = await self.redis_client.setex(key, expire, final_value)
            
            # Добавляем теги для группировки
            if tags:
                for tag in tags:
                    tag_key = f"tag:{tag}"
                    await self.redis_client.sadd(tag_key, key)
                    await self.redis_client.expire(tag_key, expire)
            
            logger.debug(f"Cache SET: {key[:50]}... (TTL: {expire}s, tags: {tags})")
            return bool(result)
        except Exception as e:
            self.errors += 1
            metrics_collector.record_cache_error()
            logger.error(f"Error setting value in cache: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Удаление значения из кеша."""
        if not self.redis_client:
            return False

        try:
            result = await self.redis_client.delete(key)
            logger.debug(f"Cache DELETE: {key[:50]}...")
            return result > 0
        except Exception as e:
            self.errors += 1
            metrics_collector.record_cache_error()
            logger.error(f"Error deleting value from cache: {e}")
            return False

    async def clear_by_tag(self, tag: str) -> int:
        """Удаление всех ключей с определенным тегом."""
        if not self.redis_client:
            return 0

        try:
            tag_key = f"tag:{tag}"
            keys = await self.redis_client.smembers(tag_key)
            
            if keys:
                # Удаляем все ключи
                deleted = await self.redis_client.delete(*keys)
                # Удаляем сам тег
                await self.redis_client.delete(tag_key)
                logger.info(f"Cleared {deleted} keys with tag '{tag}'")
                return deleted
            return 0
        except Exception as e:
            self.errors += 1
            metrics_collector.record_cache_error()
            logger.error(f"Error clearing cache by tag: {e}")
            return 0

    async def clear_pattern(self, pattern: str) -> int:
        """Удаление всех ключей, соответствующих паттерну."""
        if not self.redis_client:
            return 0

        try:
            cursor = 0
            deleted = 0
            
            # Используем SCAN для безопасного поиска ключей
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor=cursor, 
                    match=pattern, 
                    count=100
                )
                
                if keys:
                    deleted += await self.redis_client.delete(*keys)
                
                if cursor == 0:
                    break
            
            logger.info(f"Cleared {deleted} keys matching pattern '{pattern}'")
            return deleted
        except Exception as e:
            self.errors += 1
            metrics_collector.record_cache_error()
            logger.error(f"Error clearing cache pattern: {e}")
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """Получение статистики кеша."""
        stats = {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "hit_rate": self.get_hit_rate(),
            "total_requests": self.hits + self.misses,
            "connected": self.redis_client is not None,
        }
        
        if self.redis_client:
            try:
                info = await self.redis_client.info("stats")
                stats["redis_keys"] = await self.redis_client.dbsize()
                stats["redis_memory"] = info.get("used_memory_human", "N/A")
            except Exception as e:
                logger.error(f"Error getting Redis stats: {e}")
        
        return stats

    def get_hit_rate(self) -> float:
        """Вычисление hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    async def warm_cache(self, warm_func: Callable, cities: Optional[List[str]] = None):
        """
        Предварительное заполнение кеша популярными запросами.
        
        Args:
            warm_func: Асинхронная функция для получения данных
            cities: Список городов для warming (по умолчанию - популярные)
        """
        if not self.redis_client:
            logger.warning("Redis not connected, skipping cache warming")
            return

        cities_to_warm = cities or list(self.popular_cities)
        
        # Sort cities by priority for more efficient warming
        cities_to_warm.sort(key=lambda city: self.warming_priorities.get(city, 1), reverse=True)
        
        logger.info(f"Starting cache warming for {len(cities_to_warm)} cities (priority order)...")
        
        # Warm high-priority cities first, then others concurrently
        high_priority_cities = [city for city in cities_to_warm if self.warming_priorities.get(city, 0) >= 5]
        low_priority_cities = [city for city in cities_to_warm if self.warming_priorities.get(city, 0) < 5]
        
        # Warm high-priority cities sequentially to avoid overwhelming the system
        for city in high_priority_cities:
            try:
                await self._warm_city(warm_func, city)
                logger.info(f"Cache warmed for high-priority city: {city}")
                # Small delay between high-priority cities
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"Failed to warm cache for high-priority city {city}: {e}")
        
        # Warm low-priority cities concurrently
        if low_priority_cities:
            tasks = []
            for city in low_priority_cities:
                tasks.append(self._warm_city(warm_func, city))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            logger.info(
                f"Low-priority cache warming completed: {success_count}/{len(low_priority_cities)} cities cached"
            )
        
        logger.info(f"Cache warming completed for all {len(cities_to_warm)} cities")

    async def _warm_city(self, warm_func: Callable, city: str):
        """Warming кеша для одного города."""
        try:
            await warm_func(city, property_type="Квартира")
            logger.debug(f"Cache warmed for city: {city}")
        except Exception as e:
            logger.warning(f"Failed to warm cache for {city}: {e}")
            raise


# Глобальный экземпляр расширенного менеджера кеша
advanced_cache_manager = AdvancedCacheManager()


# Adaptive caching based on usage patterns
class AdaptiveCache:
    """Адаптивное кеширование на основе частоты использования."""
    
    def __init__(self):
        self.access_counts: Dict[str, int] = {}
        self.access_timestamps: Dict[str, datetime] = {}
    
    def record_access(self, key: str):
        """Записывает доступ к ключу кеша."""
        self.access_counts[key] = self.access_counts.get(key, 0) + 1
        self.access_timestamps[key] = datetime.now()
    
    def get_adaptive_ttl(self, key: str, base_ttl: int) -> int:
        """Вычисляет адаптивное время жизни на основе частоты использования."""
        access_count = self.access_counts.get(key, 0)
        
        # Increase TTL for frequently accessed items
        if access_count > 100:
            return base_ttl * 4  # 4x TTL for very popular items
        elif access_count > 50:
            return base_ttl * 2  # 2x TTL for popular items
        elif access_count > 10:
            return int(base_ttl * 1.5)  # 1.5x TTL for moderately popular items
        else:
            return base_ttl  # Default TTL
    
    def should_cache(self, key: str) -> bool:
        """Определяет, стоит ли кешировать этот ключ."""
        # For now, cache everything, but this could be extended to skip rarely used items
        return True

# Глобальный экземпляр адаптивного кеша
adaptive_cache = AdaptiveCache()


def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Генерация ключа кеша с префиксом.
    
    Args:
        prefix: Префикс ключа (например, 'parser:avito' или 'search')
        *args: Позиционные аргументы
        **kwargs: Именованные аргументы
    
    Returns:
        Хешированный ключ кеша
    """
    # Создаем строку из параметров
    params_str = f"{prefix}:{args}:{sorted(kwargs.items())}"
    # Хешируем строку для получения компактного ключа
    hash_key = hashlib.md5(params_str.encode()).hexdigest()
    return f"{prefix}:{hash_key}"


def cached_parser(expire: int = settings.CACHE_TTL, source: str = "unknown", compress: bool = True, adaptive: bool = False):
    """
    Декоратор для кеширования результатов парсера.

    Args:
        expire: Время жизни кеша в секундах
        source: Название источника парсера (для тегирования)
        compress: Сжимать данные в кеше
        adaptive: Использовать адаптивное кеширование
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Генерируем ключ кеша с префиксом парсера
            cache_key = get_cache_key(f"parser:{source}", *args, **kwargs)

            # Обеспечиваем готовность клиента кеша (lazily connect)
            if advanced_cache_manager.redis_client is None:
                await advanced_cache_manager.connect()

            # Record access for adaptive caching
            if adaptive:
                adaptive_cache.record_access(cache_key)

            # Пытаемся получить значение из кеша
            cached_result = await advanced_cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Если значения нет в кеше, вызываем функцию
            result = await func(*args, **kwargs)

            # Determine TTL for caching
            actual_expire = expire
            if adaptive:
                actual_expire = adaptive_cache.get_adaptive_ttl(cache_key, expire)

            # Сохраняем результат в кеш с тегами
            tags = [f"source:{source}", f"parser"]
            if args:
                # Предполагаем что первый аргумент - город
                tags.append(f"city:{args[0]}")
            
            await advanced_cache_manager.set(cache_key, result, actual_expire, tags=tags, compress=compress)

            return result

        return wrapper

    return decorator


def cached(expire: int = settings.CACHE_TTL, prefix: str = "default", adaptive: bool = False):
    """
    Универсальный декоратор для кеширования результатов функций.

    Args:
        expire: Время жизни кеша в секундах
        prefix: Префикс для ключа кеша
        adaptive: Использовать адаптивное кеширование
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Генерируем ключ кеша
            cache_key = get_cache_key(prefix, func.__name__, *args, **kwargs)

            # Обеспечиваем готовность клиента кеша (lazily connect)
            if advanced_cache_manager.redis_client is None:
                await advanced_cache_manager.connect()

            # Record access for adaptive caching
            if adaptive:
                adaptive_cache.record_access(cache_key)

            # Пытаемся получить значение из кеша
            cached_result = await advanced_cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Если значения нет в кеше, вызываем функцию
            result = await func(*args, **kwargs)

            # Determine TTL for caching
            actual_expire = expire
            if adaptive:
                actual_expire = adaptive_cache.get_adaptive_ttl(cache_key, expire)

            # Save result to cache with appropriate TTL
            await advanced_cache_manager.set(cache_key, result, actual_expire)

            return result

        return wrapper

    return decorator