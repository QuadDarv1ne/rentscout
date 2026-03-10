"""
Query Cache for frequently executed search queries.

Uses Redis to cache query results with intelligent invalidation.
"""
import json
import hashlib
import time
from typing import Any, Dict, List, Optional, Callable, TypeVar
from functools import wraps
import asyncio

from app.utils.logger import logger

T = TypeVar('T')


class QueryCache:
    """
    Redis-based query cache.

    Features:
    - Automatic key generation from query parameters
    - TTL-based expiration
    - Cache invalidation by pattern
    - Statistics tracking
    """

    def __init__(self, redis_client=None, default_ttl: int = 300):
        """
        Initialize query cache.

        Args:
            redis_client: Redis client (async)
            default_ttl: Default cache TTL in seconds
        """
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.prefix = "query_cache:"
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.invalidations = 0

    def _generate_key(self, query_type: str, params: Dict[str, Any]) -> str:
        """
        Generate cache key from query parameters.

        Args:
            query_type: Type of query (e.g., "search_properties")
            params: Query parameters

        Returns:
            Cache key string
        """
        # Sort params for consistent key generation
        sorted_params = sorted(params.items())
        params_str = json.dumps(sorted_params, default=str, sort_keys=True)
        
        # Create hash
        param_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]
        
        return f"{self.prefix}{query_type}:{param_hash}"

    async def get(
        self,
        query_type: str,
        params: Dict[str, Any],
        default: Any = None
    ) -> Any:
        """
        Get cached query result.

        Args:
            query_type: Type of query
            params: Query parameters
            default: Default value if not found

        Returns:
            Cached result or default
        """
        if not self.redis:
            return default

        key = self._generate_key(query_type, params)

        try:
            cached = await self.redis.get(key)
            if cached:
                self.hits += 1
                data = json.loads(cached)
                logger.debug(f"Cache hit: {key}")
                return data.get("result")
            else:
                self.misses += 1
                logger.debug(f"Cache miss: {key}")
                return default
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return default

    async def set(
        self,
        query_type: str,
        params: Dict[str, Any],
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Cache query result.

        Args:
            query_type: Type of query
            params: Query parameters
            value: Result to cache
            ttl: TTL in seconds (uses default if not specified)

        Returns:
            True if successful
        """
        if not self.redis:
            return False

        key = self._generate_key(query_type, params)
        ttl = ttl or self.default_ttl

        try:
            data = {
                "result": value,
                "cached_at": time.time(),
                "ttl": ttl,
            }
            await self.redis.setex(key, ttl, json.dumps(data, default=str))
            logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def invalidate(
        self,
        query_type: str,
        params: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Invalidate cached queries.

        Args:
            query_type: Type of query
            params: Specific params to invalidate (if None, invalidates all)

        Returns:
            Number of keys deleted
        """
        if not self.redis:
            return 0

        try:
            if params:
                # Invalidate specific key
                key = self._generate_key(query_type, params)
                count = await self.redis.delete(key)
                self.invalidations += count
                logger.debug(f"Cache invalidated: {key}")
                return count
            else:
                # Invalidate all keys of this type
                pattern = f"{self.prefix}{query_type}:*"
                keys = []
                async for key in self.redis.scan_iter(match=pattern):
                    keys.append(key)
                
                if keys:
                    count = await self.redis.delete(*keys)
                    self.invalidations += count
                    logger.debug(f"Cache invalidated {count} keys for {query_type}")
                    return count
                return 0
        except Exception as e:
            logger.error(f"Cache invalidate error: {e}")
            return 0

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate keys matching pattern.

        Args:
            pattern: Redis pattern (e.g., "query_cache:search*")

        Returns:
            Number of keys deleted
        """
        if not self.redis:
            return 0

        try:
            keys = []
            async for key in self.redis.scan_iter(match=pattern):
                keys.append(key)
            
            if keys:
                count = await self.redis.delete(*keys)
                self.invalidations += count
                logger.debug(f"Cache invalidated {count} keys matching {pattern}")
                return count
            return 0
        except Exception as e:
            logger.error(f"Cache invalidate pattern error: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "invalidations": self.invalidations,
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total,
        }

    async def clear_all(self) -> int:
        """
        Clear all query cache keys.

        Returns:
            Number of keys deleted
        """
        if not self.redis:
            return 0

        try:
            return await self.invalidate_pattern(f"{self.prefix}*")
        except Exception as e:
            logger.error(f"Cache clear all error: {e}")
            return 0


# Global cache instance
_query_cache: Optional[QueryCache] = None


def get_query_cache(redis_client=None, default_ttl: int = 300) -> QueryCache:
    """
    Get or create global query cache instance.

    Args:
        redis_client: Redis client
        default_ttl: Default TTL

    Returns:
        QueryCache instance
    """
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(redis_client, default_ttl)
    return _query_cache


def cached_query(
    query_type: str,
    ttl: int = 300,
    key_params: Optional[List[str]] = None
):
    """
    Decorator for caching query results.

    Args:
        query_type: Type of query for cache key
        ttl: Cache TTL in seconds
        key_params: List of parameter names to use in cache key
                   (if None, uses all params)

    Example:
        @cached_query("search_properties", ttl=600)
        async def search_properties(city, min_price, max_price):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            from app.utils.redis import get_redis_client
            
            cache = get_query_cache(get_redis_client(), ttl)
            
            # Get function parameters
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            # Filter params for cache key
            all_params = dict(bound.arguments)
            
            # Remove self/cls if present
            all_params.pop('self', None)
            all_params.pop('cls', None)
            
            # Use only specified key params if provided
            if key_params:
                cache_params = {
                    k: v for k, v in all_params.items() 
                    if k in key_params
                }
            else:
                cache_params = all_params
            
            # Try cache
            cached_result = await cache.get(query_type, cache_params)
            if cached_result is not None:
                return cached_result
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache.set(query_type, cache_params, result, ttl)
            
            return result
        
        return wrapper
    return decorator


__all__ = [
    "QueryCache",
    "get_query_cache",
    "cached_query",
]
