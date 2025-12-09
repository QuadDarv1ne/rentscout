"""
Background tasks for cache maintenance and cleanup.
Implements automatic cache eviction and warming strategies.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Callable

from app.utils.logger import logger
from app.utils.app_cache import app_cache

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class CacheMaintenanceTask:
    """
    Background task for automatic cache maintenance.
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        cleanup_interval: int = 3600,  # 1 hour
        max_memory_mb: int = 512
    ):
        self.redis_url = redis_url
        self.cleanup_interval = cleanup_interval
        self.max_memory_mb = max_memory_mb
        self.redis_client: Optional[aioredis.Redis] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the maintenance task."""
        if self._running:
            logger.warning("Cache maintenance already running")
            return
        
        # Initialize Redis connection
        if REDIS_AVAILABLE and self.redis_url:
            try:
                self.redis_client = await aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                await self.redis_client.ping()
                logger.info("✅ Cache maintenance connected to Redis")
            except Exception as e:
                logger.warning(f"Redis unavailable for maintenance: {e}")
                self.redis_client = None
        
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"🔄 Cache maintenance started (interval: {self.cleanup_interval}s)")
    
    async def stop(self):
        """Stop the maintenance task."""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Cache maintenance stopped")
    
    async def _run(self):
        """Main maintenance loop."""
        while self._running:
            try:
                await self._perform_maintenance()
                await asyncio.sleep(self.cleanup_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache maintenance error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retry
    
    async def _perform_maintenance(self):
        """Perform cache maintenance tasks."""
        logger.info("🧹 Starting cache maintenance")
        
        start_time = datetime.now()
        
        # 1. Clean expired keys
        await self._clean_expired_keys()
        
        # 2. Check memory usage
        await self._check_memory_usage()
        
        # 3. Log statistics
        await self._log_statistics()
        
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"✅ Cache maintenance completed in {duration:.2f}s")
    
    async def _clean_expired_keys(self):
        """Remove expired keys from cache."""
        if not self.redis_client:
            return
        
        try:
            # Get all keys with TTL
            cursor = 0
            expired_count = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor,
                    match="*",
                    count=100
                )
                
                for key in keys:
                    ttl = await self.redis_client.ttl(key)
                    # If TTL is -1 (no expiry) or very long, skip
                    if ttl == -1 or ttl > 86400:  # > 1 day
                        continue
                    
                    # If TTL is 0 or negative, key is expired
                    if ttl <= 0:
                        await self.redis_client.delete(key)
                        expired_count += 1
                
                if cursor == 0:
                    break
            
            if expired_count > 0:
                logger.info(f"Cleaned {expired_count} expired keys")
                
        except Exception as e:
            logger.error(f"Error cleaning expired keys: {e}")
    
    async def _check_memory_usage(self):
        """Check and manage Redis memory usage."""
        if not self.redis_client:
            return
        
        try:
            info = await self.redis_client.info("memory")
            used_memory_mb = info.get("used_memory", 0) / (1024 * 1024)
            
            if used_memory_mb > self.max_memory_mb:
                logger.warning(
                    f"High Redis memory usage: {used_memory_mb:.2f}MB "
                    f"(max: {self.max_memory_mb}MB)"
                )
                
                # Evict LRU keys
                await self._evict_lru_keys(target_mb=self.max_memory_mb * 0.8)
            
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")
    
    async def _evict_lru_keys(self, target_mb: float):
        """Evict least recently used keys to reach target memory."""
        if not self.redis_client:
            return
        
        try:
            # Get current memory
            info = await self.redis_client.info("memory")
            current_mb = info.get("used_memory", 0) / (1024 * 1024)
            
            if current_mb <= target_mb:
                return
            
            # Calculate how many keys to remove
            keys_to_remove = int((current_mb - target_mb) / 0.001)  # Rough estimate
            
            # Get all keys and sort by access time
            cursor = 0
            keys_with_idle = []
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor,
                    match="*",
                    count=100
                )
                
                for key in keys:
                    try:
                        idle_time = await self.redis_client.object("IDLETIME", key)
                        keys_with_idle.append((key, idle_time))
                    except:
                        pass
                
                if cursor == 0:
                    break
            
            # Sort by idle time (descending) and remove oldest
            keys_with_idle.sort(key=lambda x: x[1], reverse=True)
            
            evicted = 0
            for key, _ in keys_with_idle[:keys_to_remove]:
                await self.redis_client.delete(key)
                evicted += 1
                
                # Check if we've reached target
                info = await self.redis_client.info("memory")
                current_mb = info.get("used_memory", 0) / (1024 * 1024)
                if current_mb <= target_mb:
                    break
            
            logger.info(
                f"Evicted {evicted} LRU keys to reduce memory to {current_mb:.2f}MB"
            )
            
        except Exception as e:
            logger.error(f"Error evicting LRU keys: {e}")
    
    async def _log_statistics(self):
        """Log cache statistics."""
        try:
            # App cache stats
            app_stats = app_cache.get_stats()
            logger.info(f"App cache stats: {app_stats}")
            
            # Redis stats
            if self.redis_client:
                info = await self.redis_client.info()
                memory_mb = info.get("used_memory", 0) / (1024 * 1024)
                total_keys = await self.redis_client.dbsize()
                
                logger.info(
                    f"Redis stats: {total_keys} keys, "
                    f"{memory_mb:.2f}MB memory"
                )
        except Exception as e:
            logger.error(f"Error logging statistics: {e}")


class CacheWarmer:
    """
    Cache warming utility to pre-populate frequently accessed data.
    """
    
    def __init__(self):
        self.warmup_tasks: List[Callable] = []
    
    def register(self, func: Callable):
        """
        Register a function for cache warming.
        
        Example:
            @cache_warmer.register
            async def warm_popular_cities():
                for city in ["Москва", "Санкт-Петербург"]:
                    await search_properties(city)
        """
        self.warmup_tasks.append(func)
        return func
    
    async def warm_cache(self):
        """Execute all registered warmup tasks."""
        logger.info(f"🔥 Starting cache warmup ({len(self.warmup_tasks)} tasks)")
        
        start_time = datetime.now()
        
        results = await asyncio.gather(
            *[task() for task in self.warmup_tasks],
            return_exceptions=True
        )
        
        errors = sum(1 for r in results if isinstance(r, Exception))
        success = len(results) - errors
        
        duration = (datetime.now() - start_time).total_seconds()
        
        logger.info(
            f"✅ Cache warmup completed in {duration:.2f}s "
            f"({success} success, {errors} errors)"
        )


# Global instances
cache_maintenance = CacheMaintenanceTask()
cache_warmer = CacheWarmer()


# Example warmup tasks
@cache_warmer.register
async def warm_popular_cities():
    """Warm cache for popular cities."""
    from app.services.search import SearchService
    
    popular_cities = ["Москва", "Санкт-Петербург", "Казань", "Екатеринбург"]
    search_service = SearchService()
    
    for city in popular_cities:
        try:
            await search_service.search(city=city)
            logger.info(f"Warmed cache for {city}")
        except Exception as e:
            logger.warning(f"Failed to warm cache for {city}: {e}")
