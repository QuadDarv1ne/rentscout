"""
Кеширование на уровне приложения для часто используемых данных.
Предоставляет кеширование в памяти и Redis с автоматической инвалидацией.
"""
import asyncio
import functools
import hashlib
import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Union
from collections import OrderedDict

from app.core.config import settings
from app.utils.logger import logger

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available, using in-memory cache only")


class LRUCache:
    """Потокобезопасная реализация LRU кеша."""
    
    def __init__(self, maxsize: int = 128):
        self.cache = OrderedDict()
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Получить значение из кеша."""
        async with self._lock:
            if key in self.cache:
                self.hits += 1
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return self.cache[key]
            self.misses += 1
            return None
    
    async def set(self, key: str, value: Any) -> None:
        """Установить значение в кеш."""
        async with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            
            # Remove oldest item if cache is full
            if len(self.cache) > self.maxsize:
                self.cache.popitem(last=False)
    
    async def delete(self, key: str) -> None:
        """Удалить ключ из кеша."""
        async with self._lock:
            self.cache.pop(key, None)
    
    async def clear(self) -> None:
        """Очистить весь кеш."""
        async with self._lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> dict:
        """Получить статистику кеша."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            "size": len(self.cache),
            "maxsize": self.maxsize,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 2)
        }


class AppCache:
    """
    Многоуровневый кеш с поддержкой памяти (L1) и Redis (L2).
    """
    
    def __init__(self):
        self.memory_cache = LRUCache(maxsize=256)
        self.redis_client: Optional[aioredis.Redis] = None
        self._initialized = False
    
    async def initialize(self):
        """Инициализировать подключение к Redis."""
        if not REDIS_AVAILABLE or self._initialized:
            return
        
        try:
            self.redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False,
                max_connections=10
            )
            await self.redis_client.ping()
            self._initialized = True
            logger.info("✅ AppCache initialized with Redis L2 cache")
        except Exception as e:
            logger.warning(f"Redis unavailable, using memory cache only: {e}")
            self.redis_client = None
    
    async def close(self):
        """Закрыть подключение к Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self._initialized = False
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Сгенерировать ключ кеша из аргументов функции."""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, key: str, use_redis: bool = True) -> Optional[Any]:
        """Получить значение из кеша (L1 -> L2)."""
        # Try L1 (memory) cache first
        value = await self.memory_cache.get(key)
        if value is not None:
            return value
        
        # Try L2 (Redis) cache
        if use_redis and self.redis_client:
            try:
                redis_value = await self.redis_client.get(key)
                if redis_value:
                    value = pickle.loads(redis_value)
                    # Promote to L1 cache
                    await self.memory_cache.set(key, value)
                    return value
            except Exception as e:
                logger.warning(f"Redis get error: {e}")
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
        use_redis: bool = True
    ) -> None:
        """Установить значение в кеш (и L1, и L2)."""
        # Set in L1 (memory) cache
        await self.memory_cache.set(key, value)
        
        # Set in L2 (Redis) cache
        if use_redis and self.redis_client:
            try:
                serialized = pickle.dumps(value)
                await self.redis_client.setex(key, ttl, serialized)
            except Exception as e:
                logger.warning(f"Redis set error: {e}")
    
    async def delete(self, key: str) -> None:
        """Удалить ключ из всех уровней кеша."""
        await self.memory_cache.delete(key)
        
        if self.redis_client:
            try:
                await self.redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis delete error: {e}")
    
    async def clear(self, pattern: Optional[str] = None) -> None:
        """Очистить кеш (опционально по шаблону)."""
        await self.memory_cache.clear()
        
        if self.redis_client:
            try:
                if pattern:
                    # Delete keys matching pattern
                    keys = await self.redis_client.keys(pattern)
                    if keys:
                        await self.redis_client.delete(*keys)
                else:
                    await self.redis_client.flushdb()
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")
    
    def get_stats(self) -> dict:
        """Получить статистику кеша."""
        stats = {
            "memory_cache": self.memory_cache.get_stats(),
            "redis_available": self.redis_client is not None
        }
        return stats


# Global cache instance
app_cache = AppCache()


def cached(
    ttl: int = 300,
    prefix: str = "cache",
    use_redis: bool = True,
    key_builder: Optional[Callable] = None
):
    """
    Декоратор для кеширования результатов функции.
    
    Args:
        ttl: Время жизни в секундах
        prefix: Префикс ключа кеша
        use_redis: Использовать ли Redis L2 кеш
        key_builder: Пользовательская функция построения ключа
    
    Пример:
        @cached(ttl=600, prefix="properties")
        async def get_properties(city: str):
            return await fetch_properties(city)
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = app_cache._make_key(prefix, *args, **kwargs)
            
            # Try to get from cache
            cached_value = await app_cache.get(cache_key, use_redis=use_redis)
            if cached_value is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_value
            
            # Execute function
            logger.debug(f"Cache miss for {cache_key}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            await app_cache.set(cache_key, result, ttl=ttl, use_redis=use_redis)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str):
    """
    Декоратор для инвалидации кеша после выполнения функции.
    
    Args:
        pattern: Шаблон ключа кеша для инвалидации
    
    Пример:
        @invalidate_cache("properties:*")
        async def update_property(property_id: int):
            # Логика обновления
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            await app_cache.clear(pattern=pattern)
            logger.info(f"Cache invalidated: {pattern}")
            return result
        return wrapper
    return decorator
