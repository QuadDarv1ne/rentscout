import hashlib
import json
import logging
import pickle
from functools import wraps
from typing import Any, Callable, Optional, Union
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger(__name__)

class CacheManager:
    """Управление кэшированием с использованием Redis."""
    
    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        
    async def connect(self):
        """Подключение к Redis."""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None
            
    async def disconnect(self):
        """Отключение от Redis."""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis")
            
    async def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша."""
        if not self.redis_client:
            return None
            
        try:
            value = await self.redis_client.get(key)
            if value:
                return pickle.loads(value)
        except Exception as e:
            logger.error(f"Error getting value from cache: {e}")
        return None
        
    async def set(self, key: str, value: Any, expire: int = 300) -> bool:
        """Сохранение значения в кэше."""
        if not self.redis_client:
            return False
            
        try:
            serialized_value = pickle.dumps(value)
            result = await self.redis_client.setex(key, expire, serialized_value)
            return result
        except Exception as e:
            logger.error(f"Error setting value in cache: {e}")
            return False
            
    async def delete(self, key: str) -> bool:
        """Удаление значения из кэша."""
        if not self.redis_client:
            return False
            
        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Error deleting value from cache: {e}")
            return False
            
    async def clear_pattern(self, pattern: str) -> int:
        """Удаление всех ключей, соответствующих паттерну."""
        if not self.redis_client:
            return 0
            
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                result = await self.redis_client.delete(*keys)
                return result
            return 0
        except Exception as e:
            logger.error(f"Error clearing cache pattern: {e}")
            return 0

# Глобальный экземпляр менеджера кэша
cache_manager = CacheManager()

def get_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Генерация ключа кэша на основе имени функции и параметров."""
    # Создаем строку из параметров функции
    params_str = f"{func_name}:{args}:{sorted(kwargs.items())}"
    # Хешируем строку для получения ключа
    return hashlib.md5(params_str.encode()).hexdigest()

def cache(expire: int = 300):
    """
    Декоратор для кэширования результатов функции.
    
    Args:
        expire: Время жизни кэша в секундах (по умолчанию 300 секунд)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Генерируем ключ кэша
            cache_key = get_cache_key(func.__name__, args, kwargs)
            
            # Пытаемся получить значение из кэша
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
                
            # Если значения нет в кэше, вызываем функцию
            logger.debug(f"Cache miss for key: {cache_key}")
            result = await func(*args, **kwargs)
            
            # Сохраняем результат в кэш
            await cache_manager.set(cache_key, result, expire)
            
            return result
        return wrapper
    return decorator

# Инициализация кэша для обратной совместимости
cache = cache