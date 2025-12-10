"""Multi-level cache system with L1 (in-memory) and L2 (Redis) layers."""

from typing import Any, Optional, Dict, List, Tuple
from datetime import datetime, timedelta
import asyncio
import json
from app.utils.logger import logger
from app.services.advanced_cache import advanced_cache_manager

class MultiLevelCacheManager:
    """Manages L1 (in-memory) and L2 (Redis) caching with automatic eviction."""
    
    def __init__(self, l1_max_size: int = 1000, l1_ttl: int = 300):
        """Initialize multi-level cache manager.
        
        Args:
            l1_max_size: Maximum number of items in L1 cache
            l1_ttl: Default TTL for L1 cache in seconds
        """
        self.l1_cache: Dict[str, Tuple[Any, datetime]] = {}
        self.l1_max_size = l1_max_size
        self.l1_ttl = l1_ttl
        self.l2_manager = advanced_cache_manager
        self._access_times: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._hit_count = 0
        self._miss_count = 0
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (L1 first, then L2).
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        # Try L1 (in-memory)
        if key in self.l1_cache:
            value, expiry = self.l1_cache[key]
            if datetime.now() < expiry:
                self._access_times[key] = datetime.now().timestamp()
                self._hit_count += 1
                logger.debug(f"L1 cache HIT: {key}")
                return value
            else:
                # Expired in L1
                del self.l1_cache[key]
                if key in self._access_times:
                    del self._access_times[key]
        
        # Try L2 (Redis)
        try:
            value = await self.l2_manager.get_async(key)
            if value is not None:
                # Update L1 from L2
                async with self._lock:
                    await self._set_l1(key, value)
                self._hit_count += 1
                logger.debug(f"L2 cache HIT: {key}")
                return value
        except Exception as e:
            logger.warning(f"L2 cache error during get: {e}")
        
        self._miss_count += 1
        logger.debug(f"Cache MISS: {key}")
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Set value in both L1 and L2 caches.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
        """
        ttl = ttl or self.l1_ttl
        
        # Set L1
        async with self._lock:
            await self._set_l1(key, value, ttl)
        
        # Set L2 (Redis)
        try:
            await self.l2_manager.set_async(key, value, ttl)
            logger.debug(f"Value cached in L2: {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.warning(f"Failed to set L2 cache for {key}: {e}")
    
    async def _set_l1(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Internal L1 cache set with LRU eviction.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        ttl = ttl or self.l1_ttl
        expiry = datetime.now() + timedelta(seconds=ttl)
        
        self.l1_cache[key] = (value, expiry)
        self._access_times[key] = datetime.now().timestamp()
        
        # LRU eviction if needed
        if len(self.l1_cache) > self.l1_max_size:
            # Remove least recently used
            lru_key = min(self._access_times, key=self._access_times.get)
            del self.l1_cache[lru_key]
            del self._access_times[lru_key]
            logger.debug(f"L1 cache evicted (LRU): {lru_key}")
    
    async def delete(self, key: str) -> None:
        """Delete from both cache levels.
        
        Args:
            key: Cache key
        """
        async with self._lock:
            if key in self.l1_cache:
                del self.l1_cache[key]
            if key in self._access_times:
                del self._access_times[key]
        
        try:
            await self.l2_manager.delete_async(key)
            logger.debug(f"Deleted from cache: {key}")
        except Exception as e:
            logger.warning(f"Failed to delete from L2 cache: {e}")
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.
        
        Args:
            pattern: Pattern to match (e.g., "search:*")
            
        Returns:
            Number of keys deleted
        """
        deleted = 0
        
        # Delete from L1
        async with self._lock:
            keys_to_delete = [k for k in self.l1_cache if self._matches_pattern(k, pattern)]
            for key in keys_to_delete:
                del self.l1_cache[key]
                if key in self._access_times:
                    del self._access_times[key]
                deleted += 1
        
        # Delete from L2
        try:
            deleted_l2 = await self.l2_manager.delete_pattern_async(pattern)
            deleted += deleted_l2
        except Exception as e:
            logger.warning(f"Failed to delete pattern from L2 cache: {e}")
        
        logger.debug(f"Deleted {deleted} keys matching pattern: {pattern}")
        return deleted
    
    @staticmethod
    def _matches_pattern(key: str, pattern: str) -> bool:
        """Check if key matches pattern.
        
        Args:
            key: Cache key
            pattern: Pattern with * wildcard
            
        Returns:
            True if key matches pattern
        """
        import fnmatch
        return fnmatch.fnmatch(key, pattern)
    
    async def clear(self) -> None:
        """Clear both cache levels."""
        async with self._lock:
            self.l1_cache.clear()
            self._access_times.clear()
        
        try:
            await self.l2_manager.clear_redis()
            logger.info("Cleared all caches")
        except Exception as e:
            logger.warning(f"Failed to clear L2 cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        total_requests = self._hit_count + self._miss_count
        hit_rate = (self._hit_count / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "l1": {
                "size": len(self.l1_cache),
                "max_size": self.l1_max_size,
                "usage_percent": (len(self.l1_cache) / self.l1_max_size) * 100,
                "ttl": self.l1_ttl,
            },
            "performance": {
                "hits": self._hit_count,
                "misses": self._miss_count,
                "total_requests": total_requests,
                "hit_rate_percent": hit_rate,
            },
        }
    
    async def warm_cache(
        self,
        data: Dict[str, Any],
        ttl: Optional[int] = None,
    ) -> int:
        """Warm cache with multiple key-value pairs.
        
        Args:
            data: Dictionary of key-value pairs
            ttl: Time to live for all items
            
        Returns:
            Number of items cached
        """
        for key, value in data.items():
            await self.set(key, value, ttl)
        
        logger.info(f"Warmed cache with {len(data)} items")
        return len(data)


# Global instance
multi_level_cache = MultiLevelCacheManager()
