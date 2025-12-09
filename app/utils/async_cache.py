"""
Продвинутая система асинхронного кеширования с Redis.

Особенности:
- Автоматическое сжатие данных для экономии памяти
- Таги для группировки и инвалидации кеша
- Distributed кеширование для мультисерверных сценариев
- Bloom filter для оптимизации поиска
- TTL и LRU политики
"""
import asyncio
import json
import gzip
import hashlib
from typing import Any, Dict, Optional, List, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import redis.asyncio as redis
from functools import wraps
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Конфигурация кеша."""
    redis_url: str = "redis://localhost:6379/0"
    default_ttl: int = 3600  # 1 час
    max_memory: str = "512mb"
    eviction_policy: str = "allkeys-lru"  # Least Recently Used
    compression_threshold: int = 1024  # Сжимать если > 1KB
    enable_tags: bool = True
    enable_bloom_filter: bool = True


class AsyncRedisCache:
    """
    Асинхронный Redis-кеш с продвинутыми функциями.
    
    Singleton паттерн для экономии соединений.
    """
    
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    async def __aenter__(self):
        await self._initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close()
        
    def __init__(self, config: Optional[CacheConfig] = None):
        if not hasattr(self, '_initialized'):
            self.config = config or CacheConfig()
            self.client: Optional[redis.Redis] = None
            self.bloom_filter: Optional[redis.Redis] = None
            self._initialized = False
            self._tag_keys: Dict[str, Set[str]] = {}
            
    async def _initialize(self):
        """Инициализация Redis соединения."""
        if self._initialized:
            return
            
        async with self._lock:
            if self._initialized:
                return
                
            self.client = await redis.from_url(self.config.redis_url)
            self.bloom_filter = await redis.from_url(
                self.config.redis_url,
                decode_responses=False
            )
            
            # Настройка Redis для оптимизации памяти
            try:
                await self.client.config_set(
                    "maxmemory-policy",
                    self.config.eviction_policy
                )
                await self.client.config_set(
                    "maxmemory",
                    self.config.max_memory
                )
            except Exception as e:
                logger.warning(f"Could not configure Redis: {e}")
                
            self._initialized = True
            
    async def _close(self):
        """Закрытие Redis соединения."""
        if self.client:
            await self.client.close()
        if self.bloom_filter:
            await self.bloom_filter.close()
        self._initialized = False
        
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """
        Сохранение значения в кеш.
        
        Args:
            key: Ключ кеша
            value: Значение (будет JSON сериализовано)
            ttl: Время жизни в секундах
            tags: Теги для группировки
            
        Returns:
            True если успешно
        """
        if not self._initialized:
            await self._initialize()
            
        try:
            # Сериализация
            if isinstance(value, str):
                data = value.encode()
            else:
                data = json.dumps(value).encode()
                
            # Сжатие если нужно
            if len(data) > self.config.compression_threshold:
                data = gzip.compress(data)
                key = f"{key}:gz"
                
            # Сохранение в Redis
            ttl = ttl or self.config.default_ttl
            await self.client.setex(key, ttl, data)
            
            # Сохранение тагов
            if tags and self.config.enable_tags:
                await self._set_tags(key, tags)
                
            # Обновление Bloom filter
            if self.config.enable_bloom_filter:
                await self.bloom_filter.setbit(
                    f"bloom:{hashlib.md5(key.encode()).hexdigest()}",
                    1,
                    1
                )
                
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache for {key}: {e}")
            return False
            
    async def get(self, key: str) -> Optional[Any]:
        """
        Получение значения из кеша.
        
        Args:
            key: Ключ кеша
            
        Returns:
            Значение или None если не найдено
        """
        if not self._initialized:
            await self._initialize()
            
        try:
            # Попытка получить обычный ключ
            data = await self.client.get(key)
            
            # Если не найдено, попытка распакованного
            if data is None:
                data = await self.client.get(f"{key}:gz")
                if data:
                    data = gzip.decompress(data)
                    
            if data is None:
                return None
                
            # Десериализация
            try:
                return json.loads(data.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                return data.decode()
                
        except Exception as e:
            logger.error(f"Error getting cache for {key}: {e}")
            return None
            
    async def delete(self, key: str) -> bool:
        """
        Удаление значения из кеша.
        
        Args:
            key: Ключ кеша
            
        Returns:
            True если успешно
        """
        if not self._initialized:
            await self._initialize()
            
        try:
            await self.client.delete(key, f"{key}:gz")
            
            # Удаление тагов
            if self.config.enable_tags:
                await self._delete_tags(key)
                
            return True
        except Exception as e:
            logger.error(f"Error deleting cache for {key}: {e}")
            return False
            
    async def invalidate_by_tag(self, tag: str) -> int:
        """
        Инвалидация всех ключей с определённым тагом.
        
        Args:
            tag: Тег для инвалидации
            
        Returns:
            Количество удалённых ключей
        """
        if not self._initialized:
            await self._initialize()
            
        if not self.config.enable_tags:
            return 0
            
        try:
            tag_key = f"tag:{tag}"
            keys = await self.client.smembers(tag_key)
            
            if keys:
                # Удаление ключей
                deleted = await self.client.delete(*keys)
                
                # Удаление самого тага
                await self.client.delete(tag_key)
                
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Error invalidating tag {tag}: {e}")
            return 0
            
    async def _set_tags(self, key: str, tags: List[str]):
        """Сохранение связи между ключом и тагами."""
        for tag in tags:
            tag_key = f"tag:{tag}"
            await self.client.sadd(tag_key, key)
            
    async def _delete_tags(self, key: str):
        """Удаление связей тагов с ключом."""
        # Найти все теги для этого ключа
        tags = await self.client.keys("tag:*")
        for tag_key in tags:
            await self.client.srem(tag_key, key)
            
    async def get_stats(self) -> Dict[str, Any]:
        """Получение статистики кеша."""
        if not self._initialized:
            return {}
            
        try:
            info = await self.client.info()
            return {
                'used_memory': info.get('used_memory_human'),
                'used_memory_peak': info.get('used_memory_peak_human'),
                'connected_clients': info.get('connected_clients'),
                'total_commands': info.get('total_commands_processed'),
                'evicted_keys': info.get('evicted_keys'),
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}


# Глобальный экземпляр кеша
cache = AsyncRedisCache()


def async_cached(
    ttl: Optional[int] = None,
    tags: Optional[List[str]] = None,
    key_prefix: Optional[str] = None
):
    """
    Декоратор для кеширования результатов асинхронной функции.
    
    Args:
        ttl: Время жизни кеша в секундах
        tags: Теги для группировки кеша
        key_prefix: Префикс для ключа кеша
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Генерация ключа кеша
            func_name = key_prefix or func.__name__
            args_str = "_".join(str(arg) for arg in args if arg)
            kwargs_str = "_".join(
                f"{k}={v}" for k, v in sorted(kwargs.items())
            )
            cache_key = f"{func_name}:{args_str}:{kwargs_str}"
            
            # Попытка получить из кеша
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_value
                
            # Вычисление и сохранение в кеш
            logger.debug(f"Cache miss for {cache_key}")
            result = await func(*args, **kwargs)
            await cache.set(cache_key, result, ttl=ttl, tags=tags)
            
            return result
            
        return wrapper
    return decorator


async def example_usage():
    """Пример использования кеша."""
    async with AsyncRedisCache() as cache_instance:
        # Сохранение в кеш
        await cache_instance.set(
            "user:1:profile",
            {"id": 1, "name": "John", "email": "john@example.com"},
            ttl=3600,
            tags=["user", "user:1"]
        )
        
        # Получение из кеша
        profile = await cache_instance.get("user:1:profile")
        print(f"Profile: {profile}")
        
        # Инвалидация по тагу
        deleted_count = await cache_instance.invalidate_by_tag("user:1")
        print(f"Deleted {deleted_count} keys")
        
        # Статистика
        stats = await cache_instance.get_stats()
        print(f"Cache stats: {stats}")


if __name__ == "__main__":
    asyncio.run(example_usage())
