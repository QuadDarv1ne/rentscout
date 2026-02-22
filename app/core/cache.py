"""
Advanced Caching System for RentScout.

Multi-level caching with:
- L1: In-memory cache (asyncio.LRU)
- L2: Redis distributed cache
- Automatic cache warming
- Cache invalidation strategies
- Cache analytics

Usage:
    from app.core.cache import cache_manager
    
    @cache_manager.cached(ttl=300)
    async def get_properties(city: str):
        ...
"""

import asyncio
import hashlib
import json
import time
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import wraps
from collections import OrderedDict
import logging

from app.utils.logger import logger

# Try to import redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata."""
    value: T
    created_at: float
    expires_at: float
    hits: int = 0
    key: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return time.time() > self.expires_at
    
    def touch(self) -> None:
        """Update access time and increment hits."""
        self.hits += 1
    
    def ttl(self) -> float:
        """Get remaining TTL in seconds."""
        return max(0, self.expires_at - time.time())


class LRUCache(Generic[T]):
    """
    LRU (Least Recently Used) in-memory cache.
    
    Thread-safe for async operations.
    """
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
    
    async def get(self, key: str) -> Optional[T]:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._hits += 1
            return entry.value
    
    async def set(self, key: str, value: T, ttl: float) -> None:
        """Set value in cache."""
        async with self._lock:
            now = time.time()
            entry = CacheEntry(
                value=value,
                created_at=now,
                expires_at=now + ttl,
                key=key
            )
            
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = entry
            
            # Evict oldest if over capacity
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache."""
        async with self._lock:
            self._cache.clear()
    
    async def keys(self) -> List[str]:
        """Get all keys."""
        async with self._lock:
            return list(self._cache.keys())
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "entries": [
                {"key": k, "ttl": v.ttl(), "hits": v.hits}
                for k, v in list(self._cache.items())[:10]  # Top 10
            ]
        }


class RedisCache(Generic[T]):
    """
    Redis distributed cache.
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self) -> None:
        """Connect to Redis."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using in-memory cache only")
            return
        
        try:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis.ping()
            self._connected = True
            logger.info("✅ Redis cache connected")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            self._connected = False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._connected = False
    
    async def get(self, key: str) -> Optional[T]:
        """Get value from Redis."""
        if not self._connected:
            return None
        
        try:
            value = await self._redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: T, ttl: float) -> None:
        """Set value in Redis."""
        if not self._connected:
            return
        
        try:
            serialized = json.dumps(value)
            await self._redis.setex(key, int(ttl), serialized)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
    
    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        if not self._connected:
            return False
        
        try:
            await self._redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False
    
    async def clear(self, pattern: str = "*") -> None:
        """Clear Redis keys by pattern."""
        if not self._connected:
            return
        
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
    
    async def stats(self) -> Dict[str, Any]:
        """Get Redis statistics."""
        if not self._connected:
            return {"connected": False}
        
        try:
            info = await self._redis.info("stats")
            return {
                "connected": True,
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "used_memory": info.get("used_memory", 0),
            }
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return {"connected": False, "error": str(e)}


class CacheManager:
    """
    Multi-level cache manager.
    
    Combines L1 (in-memory) and L2 (Redis) caches.
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        l1_max_size: int = 1000,
        default_ttl: float = 300,
    ):
        self.default_ttl = default_ttl
        
        # L1: In-memory cache
        self.l1_cache: LRUCache = LRUCache(max_size=l1_max_size)
        
        # L2: Redis cache
        self.l2_cache: Optional[RedisCache] = None
        if redis_url:
            self.l2_cache = RedisCache(redis_url)
        
        # Statistics
        self._l1_hits = 0
        self._l2_hits = 0
        self._misses = 0
    
    async def initialize(self) -> None:
        """Initialize cache connections."""
        if self.l2_cache:
            await self.l2_cache.connect()
        logger.info("✅ Cache manager initialized")
    
    async def shutdown(self) -> None:
        """Shutdown cache connections."""
        if self.l2_cache:
            await self.l2_cache.disconnect()
        logger.info("✅ Cache manager shutdown complete")
    
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_parts = [prefix]
        
        # Add args
        for arg in args:
            key_parts.append(str(arg))
        
        # Add sorted kwargs
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        # Hash long keys
        key_string = ":".join(key_parts)
        if len(key_string) > 200:
            key_hash = hashlib.md5(key_string.encode()).hexdigest()[:16]
            return f"{prefix}:{key_hash}"
        
        return key_string
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (L1 -> L2)."""
        # Try L1 first
        value = await self.l1_cache.get(key)
        if value is not None:
            self._l1_hits += 1
            return value
        
        # Try L2
        if self.l2_cache:
            value = await self.l2_cache.get(key)
            if value is not None:
                self._l2_hits += 1
                # Populate L1
                await self.l1_cache.set(key, value, self.default_ttl)
                return value
        
        self._misses += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None
    ) -> None:
        """Set value in cache (L1 + L2)."""
        ttl = ttl or self.default_ttl
        
        # Set in L1
        await self.l1_cache.set(key, value, ttl)
        
        # Set in L2
        if self.l2_cache:
            await self.l2_cache.set(key, value, ttl)
    
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        await self.l1_cache.delete(key)
        if self.l2_cache:
            await self.l2_cache.delete(key)
    
    async def clear(self, pattern: str = "*") -> None:
        """Clear cache."""
        await self.l1_cache.clear()
        if self.l2_cache:
            await self.l2_cache.clear(pattern)
    
    def cached(
        self,
        ttl: Optional[float] = None,
        key_prefix: str = "cache",
        cache_none: bool = False
    ) -> Callable:
        """
        Decorator for caching function results.
        
        Args:
            ttl: Cache TTL in seconds
            key_prefix: Prefix for cache keys
            cache_none: Whether to cache None values
        
        Example:
            @cache_manager.cached(ttl=300, key_prefix="properties")
            async def get_properties(city: str):
                ...
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                key = self._make_key(
                    key_prefix,
                    func.__name__,
                    *args,
                    **kwargs
                )
                
                # Try cache
                value = await self.get(key)
                if value is not None or (value is None and cache_none):
                    logger.debug(f"Cache hit: {key}")
                    return value
                
                # Call function
                result = await func(*args, **kwargs)
                
                # Cache result
                if result is not None or cache_none:
                    await self.set(key, result, ttl)
                
                return result
            
            return wrapper
        return decorator
    
    async def warm_cache(
        self,
        keys: List[str],
        loader: Callable,
        ttl: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Warm cache with pre-computed values.
        
        Args:
            keys: List of keys to warm
            loader: Async function to load values
            ttl: Cache TTL
        
        Returns:
            Warming statistics
        """
        start = time.time()
        loaded = 0
        errors = 0
        
        for key in keys:
            try:
                value = await loader(key)
                await self.set(key, value, ttl)
                loaded += 1
            except Exception as e:
                logger.error(f"Cache warming error for {key}: {e}")
                errors += 1
        
        duration = time.time() - start
        logger.info(f"Cache warming complete: {loaded} loaded, {errors} errors in {duration:.2f}s")
        
        return {
            "duration": duration,
            "loaded": loaded,
            "errors": errors
        }
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._l1_hits + self._l2_hits + self._misses
        hit_rate = (self._l1_hits + self._l2_hits) / total if total > 0 else 0
        
        return {
            "l1_hits": self._l1_hits,
            "l2_hits": self._l2_hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "l1_stats": self.l1_cache.stats(),
            "l2_stats": asyncio.create_task(self.l2_cache.stats()) if self.l2_cache else None
        }


# Global cache manager instance
cache_manager = CacheManager(
    default_ttl=300,
    l1_max_size=1000
)


__all__ = [
    "CacheManager",
    "LRUCache",
    "RedisCache",
    "CacheEntry",
    "cache_manager",
]
