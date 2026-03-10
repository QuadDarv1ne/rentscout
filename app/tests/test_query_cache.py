"""
Tests for Query Cache implementation.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.utils.query_cache import QueryCache, get_query_cache, cached_query


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.scan_iter = MagicMock()
    return redis


@pytest.fixture
def query_cache(mock_redis):
    """Create QueryCache instance with mock Redis."""
    return QueryCache(redis_client=mock_redis, default_ttl=300)


@pytest.mark.asyncio
async def test_query_cache_init(query_cache):
    """Test QueryCache initialization."""
    assert query_cache.default_ttl == 300
    assert query_cache.prefix == "query_cache:"
    assert query_cache.hits == 0
    assert query_cache.misses == 0


@pytest.mark.asyncio
async def test_generate_key(query_cache):
    """Test cache key generation."""
    params = {"city": "Москва", "min_price": 10000}
    key = query_cache._generate_key("search", params)
    
    assert key.startswith("query_cache:search:")
    assert len(key) > 20
    
    # Same params should generate same key
    key2 = query_cache._generate_key("search", params)
    assert key == key2
    
    # Different params should generate different key
    params2 = {"city": "СПб", "min_price": 10000}
    key3 = query_cache._generate_key("search", params2)
    assert key != key3


@pytest.mark.asyncio
async def test_cache_get_hit(query_cache, mock_redis):
    """Test cache get with hit."""
    import json
    mock_redis.get.return_value = json.dumps({"result": "test_data", "cached_at": 12345})
    
    result = await query_cache.get("search", {"city": "Москва"})
    
    assert result == "test_data"
    assert query_cache.hits == 1
    mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_cache_get_miss(query_cache, mock_redis):
    """Test cache get with miss."""
    mock_redis.get.return_value = None
    
    result = await query_cache.get("search", {"city": "Москва"}, default="default")
    
    assert result == "default"
    assert query_cache.misses == 1
    mock_redis.get.assert_called_once()


@pytest.mark.asyncio
async def test_cache_get_no_redis():
    """Test cache get without Redis."""
    cache = QueryCache(redis_client=None)
    result = await cache.get("search", {"city": "Москва"}, default="default")
    assert result == "default"


@pytest.mark.asyncio
async def test_cache_set(query_cache, mock_redis):
    """Test cache set."""
    mock_redis.setex.return_value = True
    
    result = await query_cache.set("search", {"city": "Москва"}, "test_data", ttl=600)
    
    assert result is True
    mock_redis.setex.assert_called_once()
    
    # Check setex arguments
    args = mock_redis.setex.call_args
    assert args[0][1] == 600  # TTL


@pytest.mark.asyncio
async def test_cache_set_no_redis():
    """Test cache set without Redis."""
    cache = QueryCache(redis_client=None)
    result = await cache.set("search", {"city": "Москва"}, "test_data")
    assert result is False


@pytest.mark.asyncio
async def test_cache_invalidate_specific(query_cache, mock_redis):
    """Test cache invalidation with specific params."""
    mock_redis.delete.return_value = 1
    
    count = await query_cache.invalidate("search", {"city": "Москва"})
    
    assert count == 1
    mock_redis.delete.assert_called_once()


@pytest.mark.asyncio
async def test_cache_invalidate_all(query_cache, mock_redis):
    """Test cache invalidation for all keys of type."""
    # Mock scan_iter
    mock_redis.scan_iter.return_value.__aiter__.return_value = [
        "query_cache:search:abc123",
        "query_cache:search:def456",
    ]
    mock_redis.delete.return_value = 2
    
    count = await query_cache.invalidate("search")
    
    assert count == 2
    assert query_cache.invalidations == 2


@pytest.mark.asyncio
async def test_cache_invalidate_no_redis():
    """Test cache invalidation without Redis."""
    cache = QueryCache(redis_client=None)
    count = await cache.invalidate("search")
    assert count == 0


@pytest.mark.asyncio
async def test_cache_get_stats(query_cache):
    """Test cache statistics."""
    query_cache.hits = 80
    query_cache.misses = 20
    query_cache.invalidations = 5
    
    stats = query_cache.get_stats()
    
    assert stats["hits"] == 80
    assert stats["misses"] == 20
    assert stats["invalidations"] == 5
    assert stats["hit_rate_percent"] == 80.0
    assert stats["total_requests"] == 100


@pytest.mark.asyncio
async def test_cache_clear_all(query_cache, mock_redis):
    """Test clearing all cache."""
    mock_redis.scan_iter.return_value.__aiter__.return_value = [
        "query_cache:search:abc123",
        "query_cache:parser:def456",
    ]
    mock_redis.delete.return_value = 2
    
    count = await query_cache.clear_all()
    
    assert count == 2


@pytest.mark.asyncio
async def test_get_query_cache_singleton():
    """Test that get_query_cache returns singleton."""
    cache1 = get_query_cache()
    cache2 = get_query_cache()
    assert cache1 is cache2


@pytest.mark.asyncio
async def test_cached_query_decorator():
    """Test @cached_query decorator."""
    from app.utils.query_cache import get_query_cache
    
    with patch('app.utils.query_cache.get_redis_client') as mock_get_redis:
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # Cache miss
        mock_redis.setex.return_value = True
        mock_get_redis.return_value = mock_redis
        
        call_count = 0
        
        @cached_query("test_query", ttl=300)
        async def test_func(value):
            nonlocal call_count
            call_count += 1
            return f"result_{value}"
        
        # First call - cache miss
        result1 = await test_func("test")
        assert result1 == "result_test"
        assert call_count == 1
        
        # Second call - should use cache (but mock returns None)
        result2 = await test_func("test")
        assert call_count == 2  # Still 2 because cache returns None


@pytest.mark.asyncio
async def test_cache_error_handling(query_cache, mock_redis):
    """Test cache handles errors gracefully."""
    mock_redis.get.side_effect = Exception("Redis error")
    
    # Should not raise, should return default
    result = await query_cache.get("search", {"city": "Москва"}, default="default")
    assert result == "default"
    
    mock_redis.setex.side_effect = Exception("Redis error")
    
    # Should not raise, should return False
    result = await query_cache.set("search", {"city": "Москва"}, "data")
    assert result is False
