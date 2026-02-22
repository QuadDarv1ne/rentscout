"""
Tests for advanced caching system.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.cache import (
    CacheEntry,
    LRUCache,
    CacheManager,
    cache_manager,
    REDIS_AVAILABLE,
)


class TestCacheEntry:
    """Tests for CacheEntry."""

    def test_create_entry(self):
        """Test creating cache entry."""
        entry = CacheEntry(
            value="test",
            created_at=time.time(),
            expires_at=time.time() + 60
        )
        assert entry.value == "test"
        assert entry.hits == 0
        assert not entry.is_expired()

    def test_entry_expired(self):
        """Test expired entry."""
        entry = CacheEntry(
            value="test",
            created_at=time.time() - 120,
            expires_at=time.time() - 60
        )
        assert entry.is_expired()

    def test_entry_touch(self):
        """Test touching entry."""
        entry = CacheEntry(
            value="test",
            created_at=time.time(),
            expires_at=time.time() + 60
        )
        assert entry.hits == 0
        entry.touch()
        assert entry.hits == 1

    def test_entry_ttl(self):
        """Test entry TTL."""
        entry = CacheEntry(
            value="test",
            created_at=time.time(),
            expires_at=time.time() + 60
        )
        ttl = entry.ttl()
        assert 59 <= ttl <= 60


@pytest.mark.asyncio
class TestLRUCache:
    """Tests for LRU cache."""

    async def test_set_get(self):
        """Test basic set/get."""
        cache = LRUCache(max_size=10)
        await cache.set("key1", "value1", ttl=60)
        result = await cache.get("key1")
        assert result == "value1"

    async def test_get_missing(self):
        """Test getting missing key."""
        cache = LRUCache(max_size=10)
        result = await cache.get("nonexistent")
        assert result is None

    async def test_expired_entry(self):
        """Test expired entry."""
        cache = LRUCache(max_size=10)
        await cache.set("key1", "value1", ttl=0.01)
        await asyncio.sleep(0.02)
        result = await cache.get("key1")
        assert result is None

    async def test_lru_eviction(self):
        """Test LRU eviction."""
        cache = LRUCache(max_size=3)
        await cache.set("key1", "value1", ttl=60)
        await cache.set("key2", "value2", ttl=60)
        await cache.set("key3", "value3", ttl=60)
        await cache.set("key4", "value4", ttl=60)  # Should evict key1
        
        result1 = await cache.get("key1")
        result4 = await cache.get("key4")
        assert result1 is None  # Evicted
        assert result4 == "value4"

    async def test_delete(self):
        """Test delete."""
        cache = LRUCache(max_size=10)
        await cache.set("key1", "value1", ttl=60)
        deleted = await cache.delete("key1")
        assert deleted is True
        result = await cache.get("key1")
        assert result is None

    async def test_clear(self):
        """Test clear."""
        cache = LRUCache(max_size=10)
        await cache.set("key1", "value1", ttl=60)
        await cache.set("key2", "value2", ttl=60)
        await cache.clear()
        keys = await cache.keys()
        assert len(keys) == 0

    async def test_stats(self):
        """Test statistics."""
        cache = LRUCache(max_size=10)
        await cache.set("key1", "value1", ttl=60)
        await cache.get("key1")  # Hit
        await cache.get("key1")  # Hit
        await cache.get("nonexistent")  # Miss
        
        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2/3


@pytest.mark.asyncio
class TestCacheManager:
    """Tests for cache manager."""

    async def test_basic_set_get(self):
        """Test basic set/get."""
        manager = CacheManager()
        await manager.initialize()
        
        await manager.set("key1", "value1", ttl=60)
        result = await manager.get("key1")
        assert result == "value1"
        
        await manager.shutdown()

    async def test_cache_miss(self):
        """Test cache miss."""
        manager = CacheManager()
        await manager.initialize()
        
        result = await manager.get("nonexistent")
        assert result is None
        
        await manager.shutdown()

    async def test_delete(self):
        """Test delete."""
        manager = CacheManager()
        await manager.initialize()
        
        await manager.set("key1", "value1", ttl=60)
        await manager.delete("key1")
        result = await manager.get("key1")
        assert result is None
        
        await manager.shutdown()

    async def test_clear(self):
        """Test clear."""
        manager = CacheManager()
        await manager.initialize()
        
        await manager.set("key1", "value1", ttl=60)
        await manager.set("key2", "value2", ttl=60)
        await manager.clear()
        
        result1 = await manager.get("key1")
        result2 = await manager.get("key2")
        assert result1 is None
        assert result2 is None
        
        await manager.shutdown()

    async def test_cached_decorator(self):
        """Test cached decorator."""
        manager = CacheManager()
        await manager.initialize()
        
        call_count = 0
        
        @manager.cached(ttl=60, key_prefix="test")
        async def get_data(value: int):
            nonlocal call_count
            call_count += 1
            return value * 2
        
        # First call - cache miss
        result1 = await get_data(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call - cache hit
        result2 = await get_data(5)
        assert result2 == 10
        assert call_count == 1  # Not called again
        
        # Different args - cache miss
        result3 = await get_data(10)
        assert result3 == 20
        assert call_count == 2
        
        await manager.shutdown()

    async def test_warm_cache(self):
        """Test cache warming."""
        manager = CacheManager()
        await manager.initialize()
        
        keys = ["key1", "key2", "key3"]
        
        async def loader(key):
            return f"value_{key}"
        
        stats = await manager.warm_cache(keys, loader, ttl=60)
        
        assert stats["loaded"] == 3
        assert stats["errors"] == 0
        
        # Verify values are cached
        for key in keys:
            result = await manager.get(key)
            assert result == f"value_{key}"
        
        await manager.shutdown()

    async def test_stats(self):
        """Test statistics."""
        manager = CacheManager()
        await manager.initialize()
        
        await manager.set("key1", "value1", ttl=60)
        await manager.get("key1")  # Hit
        await manager.get("nonexistent")  # Miss
        
        stats = manager.stats()
        assert "l1_hits" in stats
        assert "l2_hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        
        await manager.shutdown()

    async def test_make_key(self):
        """Test key generation."""
        manager = CacheManager()
        
        key1 = manager._make_key("prefix", "arg1", "arg2")
        key2 = manager._make_key("prefix", "arg1", "arg2")
        key3 = manager._make_key("prefix", "arg1", "arg3")
        
        assert key1 == key2
        assert key1 != key3

    async def test_make_key_long(self):
        """Test key generation for long arguments."""
        manager = CacheManager()
        
        long_arg = "x" * 300
        key = manager._make_key("prefix", long_arg)
        
        # Should be hashed and short
        assert len(key) < 200
        assert "prefix:" in key


class TestCacheManagerWithoutRedis:
    """Tests for cache manager without Redis."""

    @pytest.mark.asyncio
    async def test_no_redis_fallback(self):
        """Test fallback to L1 cache without Redis."""
        manager = CacheManager(redis_url=None)
        await manager.initialize()
        
        # Should work with L1 only
        await manager.set("key1", "value1", ttl=60)
        result = await manager.get("key1")
        assert result == "value1"
        
        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_redis_not_available(self):
        """Test when Redis is not available."""
        if not REDIS_AVAILABLE:
            manager = CacheManager(redis_url="redis://localhost:6379")
            await manager.initialize()
            
            # Should work with L1 only
            await manager.set("key1", "value1", ttl=60)
            result = await manager.get("key1")
            assert result == "value1"
            
            await manager.shutdown()


class TestGlobalCacheManager:
    """Tests for global cache manager instance."""

    def test_global_instance_exists(self):
        """Test global instance exists."""
        assert cache_manager is not None
        assert isinstance(cache_manager, CacheManager)

    def test_global_instance_default_ttl(self):
        """Test global instance default TTL."""
        assert cache_manager.default_ttl == 300
