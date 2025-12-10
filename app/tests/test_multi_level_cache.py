"""Tests for multi-level cache system."""

import pytest
from datetime import datetime, timedelta
from app.services.multi_level_cache import MultiLevelCacheManager


@pytest.fixture
def cache_manager():
    """Create a fresh cache manager for testing."""
    return MultiLevelCacheManager(l1_max_size=10, l1_ttl=300)


@pytest.mark.asyncio
async def test_cache_set_get(cache_manager):
    """Test basic set/get operations."""
    await cache_manager.set("test_key", "test_value")
    result = await cache_manager.get("test_key")
    assert result == "test_value"


@pytest.mark.asyncio
async def test_cache_miss(cache_manager):
    """Test cache miss returns None."""
    result = await cache_manager.get("nonexistent_key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_expiration(cache_manager):
    """Test that expired entries are removed."""
    # Set with 1 second TTL
    await cache_manager.set("expiring_key", "value", ttl=1)
    
    # Should exist immediately
    result = await cache_manager.get("expiring_key")
    assert result == "value"
    
    # Wait for expiration
    import asyncio
    await asyncio.sleep(1.1)
    
    # Should be expired
    result = await cache_manager.get("expiring_key")
    assert result is None


@pytest.mark.asyncio
async def test_lru_eviction(cache_manager):
    """Test LRU eviction when cache is full."""
    # Fill cache to capacity
    for i in range(10):
        await cache_manager.set(f"key_{i}", f"value_{i}")
    
    # Cache should be at max
    assert len(cache_manager.l1_cache) == 10
    
    # Add one more item - should evict LRU
    await cache_manager.set("key_10", "value_10")
    
    # Should still be at max
    assert len(cache_manager.l1_cache) == 10


@pytest.mark.asyncio
async def test_cache_delete(cache_manager):
    """Test cache deletion."""
    await cache_manager.set("to_delete", "value")
    assert await cache_manager.get("to_delete") == "value"
    
    await cache_manager.delete("to_delete")
    assert await cache_manager.get("to_delete") is None


@pytest.mark.asyncio
async def test_cache_clear(cache_manager):
    """Test clearing entire cache."""
    # Add multiple items
    for i in range(5):
        await cache_manager.set(f"key_{i}", f"value_{i}")
    
    assert len(cache_manager.l1_cache) > 0
    
    # Clear cache
    await cache_manager.clear()
    
    assert len(cache_manager.l1_cache) == 0


@pytest.mark.asyncio
async def test_cache_stats(cache_manager):
    """Test cache statistics."""
    await cache_manager.set("key1", "value1")
    await cache_manager.get("key1")  # Hit
    await cache_manager.get("key2")  # Miss
    
    stats = cache_manager.get_stats()
    
    assert stats["l1"]["size"] == 1
    assert stats["performance"]["hits"] > 0
    assert stats["performance"]["misses"] > 0


@pytest.mark.asyncio
async def test_cache_pattern_matching(cache_manager):
    """Test pattern matching for cache deletion."""
    # Add items with matching patterns
    await cache_manager.set("search:moscow:1", "value1")
    await cache_manager.set("search:moscow:2", "value2")
    await cache_manager.set("search:spb:1", "value3")
    
    # Delete matching pattern
    deleted = await cache_manager.delete_pattern("search:moscow:*")
    
    assert deleted >= 2
    assert await cache_manager.get("search:moscow:1") is None
    assert await cache_manager.get("search:spb:1") is not None


@pytest.mark.asyncio
async def test_cache_warm(cache_manager):
    """Test cache warming with multiple items."""
    data = {
        f"key_{i}": f"value_{i}"
        for i in range(5)
    }
    
    count = await cache_manager.warm_cache(data)
    
    assert count == 5
    
    # Verify all items are cached
    for i in range(5):
        assert await cache_manager.get(f"key_{i}") == f"value_{i}"


@pytest.mark.asyncio
async def test_cache_concurrent_access(cache_manager):
    """Test concurrent cache access."""
    import asyncio
    
    async def access_cache(key: str, value: str):
        await cache_manager.set(key, value)
        return await cache_manager.get(key)
    
    # Run concurrent accesses
    tasks = [
        access_cache(f"key_{i}", f"value_{i}")
        for i in range(10)
    ]
    
    results = await asyncio.gather(*tasks)
    
    # All should succeed
    assert len(results) == 10
    assert all(r is not None for r in results)


@pytest.mark.asyncio
async def test_cache_with_complex_objects(cache_manager):
    """Test caching complex objects."""
    data = {
        "id": 123,
        "properties": [
            {"name": "prop1", "value": 100},
            {"name": "prop2", "value": 200},
        ],
        "metadata": {
            "created": "2025-12-10",
            "source": "test",
        }
    }
    
    await cache_manager.set("complex", data)
    result = await cache_manager.get("complex")
    
    assert result == data
    assert result["properties"][0]["name"] == "prop1"
