"""
Tests for Cache Management endpoints.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.info = AsyncMock(return_value={
        "used_memory_human": "10M",
    })
    redis.scan_iter = MagicMock()
    redis.scan_iter.return_value.__aiter__.return_value = []
    redis.delete = AsyncMock(return_value=0)
    return redis


@pytest.mark.asyncio
async def test_get_cache_stats(client, mock_redis):
    """Test getting cache statistics."""
    with patch('app.utils.redis.get_redis_client', return_value=mock_redis):
        response = client.get("/cache/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "redis_connected" in data
        assert "total_keys" in data
        assert "memory_used" in data


@pytest.mark.asyncio
async def test_get_cache_stats_no_redis(client):
    """Test cache stats when Redis is not available."""
    with patch('app.utils.redis.get_redis_client', return_value=None):
        response = client.get("/cache/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["redis_connected"] is False


@pytest.mark.asyncio
async def test_clear_cache(client, mock_redis):
    """Test clearing cache."""
    mock_redis.scan_iter.return_value.__aiter__.return_value = [
        "cache:key1",
        "cache:key2",
    ]
    mock_redis.delete = AsyncMock(return_value=2)
    
    with patch('app.utils.redis.get_redis_client', return_value=mock_redis):
        response = client.post(
            "/cache/clear",
            json={"pattern": "cache:*"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["cleared"] is True
        assert data["keys_deleted"] >= 0


@pytest.mark.asyncio
async def test_clear_cache_by_prefix(client, mock_redis):
    """Test clearing cache by prefix."""
    mock_redis.scan_iter.return_value.__aiter__.return_value = ["query_cache:abc123"]
    mock_redis.delete = AsyncMock(return_value=1)
    
    with patch('app.utils.redis.get_redis_client', return_value=mock_redis):
        response = client.post(
            "/cache/clear",
            json={"prefix": "query_cache:"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["cleared"] is True


@pytest.mark.asyncio
async def test_invalidate_cache(client):
    """Test invalidating specific cache."""
    with patch('app.utils.query_cache.get_query_cache') as mock_get_cache:
        mock_cache = MagicMock()
        mock_cache.invalidate = AsyncMock(return_value=5)
        mock_get_cache.return_value = mock_cache
        
        response = client.post(
            "/cache/invalidate?query_type=search_properties"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["invalidated"] is True
        assert data["keys_deleted"] == 5


@pytest.mark.asyncio
async def test_invalidate_cache_with_params(client):
    """Test invalidating cache with specific params."""
    import json
    with patch('app.utils.query_cache.get_query_cache') as mock_get_cache:
        mock_cache = MagicMock()
        mock_cache.invalidate = AsyncMock(return_value=1)
        mock_get_cache.return_value = mock_cache
        
        params = json.dumps({"city": "Москва"})
        response = client.post(
            f"/cache/invalidate?query_type=search&params={params}"
        )
        
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_invalidate_cache_invalid_json(client):
    """Test invalidating cache with invalid JSON."""
    response = client.post(
        "/cache/invalidate?query_type=search&params=invalid_json"
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_cache_keys(client, mock_redis):
    """Test listing cache keys."""
    mock_redis.scan_iter.return_value.__aiter__.return_value = [
        "cache:key1",
        "cache:key2",
        "cache:key3",
    ]
    
    with patch('app.utils.redis.get_redis_client', return_value=mock_redis):
        response = client.get("/cache/keys?pattern=cache:*")
        
        assert response.status_code == 200
        data = response.json()
        assert "keys" in data
        assert "total" in data
        assert len(data["keys"]) <= 100


@pytest.mark.asyncio
async def test_list_cache_keys_limit(client, mock_redis):
    """Test listing cache keys with limit."""
    keys = [f"cache:key{i}" for i in range(200)]
    mock_redis.scan_iter.return_value.__aiter__.return_value = keys
    
    with patch('app.utils.redis.get_redis_client', return_value=mock_redis):
        response = client.get("/cache/keys?limit=50")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["keys"]) <= 50


@pytest.mark.asyncio
async def test_warm_cache(client):
    """Test warming cache."""
    with patch('app.services.optimized_search.OptimizedSearchService') as MockService:
        mock_service = MagicMock()
        mock_service.search_cached = AsyncMock(return_value=([], False, {}))
        MockService.return_value = mock_service
        
        queries = [
            {"city": "Москва", "property_type": "Квартира"},
            {"city": "СПб", "property_type": "Квартира"},
        ]
        
        response = client.post(
            "/cache/warm",
            json={"queries": queries}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "warmed" in data
        assert "errors" in data


@pytest.mark.asyncio
async def test_warm_cache_empty(client):
    """Test warming cache with empty queries."""
    response = client.post(
        "/cache/warm",
        json={"queries": []}
    )
    
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_clear_cache_no_redis(client):
    """Test clearing cache when Redis is not available."""
    with patch('app.utils.redis.get_redis_client', return_value=None):
        response = client.post(
            "/cache/clear",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["cleared"] is False
        assert data["keys_deleted"] == 0
