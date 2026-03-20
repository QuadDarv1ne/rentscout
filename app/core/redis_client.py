"""
Redis Client with Connection Pool.

Централизованное кэширование с поддержкой:
- Connection pool
- Автоматическое переподключение
- Сериализация/десериализация JSON
- Rate limiting
- Метрики использования
"""

import json
import time
from typing import Any, Optional, Dict, List
from datetime import timedelta
import logging

from app.core.config import settings
from app.utils.logger import logger

# Try to import redis
try:
    import redis.asyncio as redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    
    class RedisError(Exception):
        pass
    
    class RedisConnectionError(Exception):
        pass


class RedisClient:
    """Redis клиент с connection pool."""
    
    def __init__(self):
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None
        self._connected = False
        self._stats = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "sets": 0,
            "deletes": 0,
        }
    
    async def connect(self) -> bool:
        """
        Подключение к Redis.

        Returns:
            True если успешно
        """
        if not REDIS_AVAILABLE:
            logger.warning("Redis library not available")
            return False
        
        if not settings.REDIS_URL:
            logger.warning("REDIS_URL not configured")
            return False
        
        try:
            # Создаем connection pool
            self._pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            
            # Создаем клиент
            self._client = redis.Redis(
                connection_pool=self._pool,
                decode_responses=True,
            )
            
            # Проверяем подключение
            await self._client.ping()
            self._connected = True
            
            logger.info(f"Connected to Redis: {settings.REDIS_URL}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            return False
    
    async def disconnect(self):
        """Отключение от Redis."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
        self._connected = False
        logger.info("Disconnected from Redis")
    
    async def _ensure_connected(self):
        """Проверка и восстановление подключения."""
        if not self._connected:
            await self.connect()
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Получение значения из кэша.

        Args:
            key: Ключ

        Returns:
            Значение или None
        """
        try:
            await self._ensure_connected()
            
            if not self._client:
                return None
            
            value = await self._client.get(key)
            
            if value is None:
                self._stats["misses"] += 1
                return None
            
            self._stats["hits"] += 1
            
            # Пытаемся десериализовать JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
                
        except RedisError as e:
            self._stats["errors"] += 1
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None,
    ) -> bool:
        """
        Установка значения в кэш.

        Args:
            key: Ключ
            value: Значение
            expire: TTL в секундах

        Returns:
            True если успешно
        """
        try:
            await self._ensure_connected()
            
            if not self._client:
                return False
            
            # Сериализуем в JSON
            if isinstance(value, (dict, list, bool, int, float)):
                value = json.dumps(value, ensure_ascii=False)
            
            # Устанавливаем значение
            if expire:
                result = await self._client.setex(key, expire, value)
            else:
                result = await self._client.set(key, value)
            
            self._stats["sets"] += 1
            return bool(result)
            
        except RedisError as e:
            self._stats["errors"] += 1
            logger.error(f"Redis set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Удаление ключа.

        Args:
            key: Ключ

        Returns:
            True если ключ существовал
        """
        try:
            await self._ensure_connected()
            
            if not self._client:
                return False
            
            result = await self._client.delete(key)
            self._stats["deletes"] += 1
            return result > 0
            
        except RedisError as e:
            self._stats["errors"] += 1
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Проверка существования ключа.

        Args:
            key: Ключ

        Returns:
            True если ключ существует
        """
        try:
            await self._ensure_connected()
            
            if not self._client:
                return False
            
            return bool(await self._client.exists(key))
            
        except RedisError as e:
            self._stats["errors"] += 1
            logger.error(f"Redis exists error: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        Установка TTL для ключа.

        Args:
            key: Ключ
            seconds: TTL в секундах

        Returns:
            True если успешно
        """
        try:
            await self._ensure_connected()
            
            if not self._client:
                return False
            
            return bool(await self._client.expire(key, seconds))
            
        except RedisError as e:
            self._stats["errors"] += 1
            logger.error(f"Redis expire error: {e}")
            return False
    
    async def incr(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Инкремент значения.

        Args:
            key: Ключ
            amount: На сколько увеличить

        Returns:
            Новое значение
        """
        try:
            await self._ensure_connected()
            
            if not self._client:
                return None
            
            return await self._client.incr(key, amount)
            
        except RedisError as e:
            self._stats["errors"] += 1
            logger.error(f"Redis incr error: {e}")
            return None
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Получение нескольких значений.

        Args:
            keys: Список ключей

        Returns:
            Словарь {key: value}
        """
        try:
            await self._ensure_connected()
            
            if not self._client:
                return {}
            
            values = await self._client.mget(keys)
            
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    self._stats["hits"] += 1
                    try:
                        result[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        result[key] = value
                else:
                    self._stats["misses"] += 1
            
            return result
            
        except RedisError as e:
            self._stats["errors"] += 1
            logger.error(f"Redis get_many error: {e}")
            return {}
    
    async def set_many(self, mapping: Dict[str, Any], expire: Optional[int] = None):
        """
        Установка нескольких значений.

        Args:
            mapping: Словарь {key: value}
            expire: TTL в секундах
        """
        try:
            await self._ensure_connected()
            
            if not self._client:
                return
            
            # Сериализуем значения
            serialized = {}
            for key, value in mapping.items():
                if isinstance(value, (dict, list, bool, int, float)):
                    value = json.dumps(value, ensure_ascii=False)
                serialized[key] = value
            
            # Устанавливаем
            if serialized:
                await self._client.mset(serialized)
                self._stats["sets"] += len(serialized)
                
                # Устанавливаем TTL если нужно
                if expire:
                    for key in serialized.keys():
                        await self._client.expire(key, expire)
            
        except RedisError as e:
            self._stats["errors"] += 1
            logger.error(f"Redis set_many error: {e}")
    
    async def clear_pattern(self, pattern: str) -> int:
        """
        Очистка ключей по паттерну.

        Args:
            pattern: Паттерн (например, "cache:*")

        Returns:
            Количество удалённых ключей
        """
        try:
            await self._ensure_connected()
            
            if not self._client:
                return 0
            
            # Находим ключи по паттерну
            keys = await self._client.keys(pattern)
            
            if not keys:
                return 0
            
            # Удаляем
            return await self._client.delete(*keys)
            
        except RedisError as e:
            self._stats["errors"] += 1
            logger.error(f"Redis clear_pattern error: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику использования.

        Returns:
            Статистика
        """
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate_percent": round(hit_rate, 2),
            "connected": self._connected,
        }
    
    @property
    def is_connected(self) -> bool:
        """Проверка подключения."""
        return self._connected


# Глобальный экземпляр
redis_client = RedisClient()


__all__ = [
    "redis_client",
    "RedisClient",
    "REDIS_AVAILABLE",
]
