"""
Тесты для Redis Client.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.redis_client import (
    redis_client,
    RedisClient,
    REDIS_AVAILABLE,
)


@pytest.fixture
def mock_redis():
    """Фикстура для mock Redis."""
    with patch('app.core.redis_client.redis') as mock:
        mock.Redis = MagicMock()
        mock.ConnectionPool = MagicMock()
        yield mock


class TestRedisClientInit:
    """Тесты инициализации Redis клиента."""

    def test_client_creation(self):
        """Тест создания клиента."""
        client = RedisClient()
        
        assert client._pool is None
        assert client._client is None
        assert client._connected is False

    def test_initial_stats(self):
        """Тест начальной статистики."""
        client = RedisClient()
        stats = client.get_stats()
        
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["errors"] == 0
        assert stats["connected"] is False


class TestRedisClientConnect:
    """Тесты подключения."""

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_redis):
        """Тест успешного подключения."""
        client = RedisClient()
        
        # Настраиваем mock
        mock_instance = AsyncMock()
        mock_instance.ping = AsyncMock()
        mock_redis.Redis.return_value = mock_instance
        
        with patch.object(client, '_pool', MagicMock()):
            result = await client.connect()
            
            # Проверяем что ping был вызван
            mock_instance.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_no_redis_url(self):
        """Тест подключения без REDIS_URL."""
        with patch('app.core.redis_client.settings') as mock_settings:
            mock_settings.REDIS_URL = ""
            
            client = RedisClient()
            result = await client.connect()
            
            assert result is False

    @pytest.mark.asyncio
    async def test_connect_no_redis_library(self):
        """Тест подключения без библиотеки redis."""
        with patch('app.core.redis_client.REDIS_AVAILABLE', False):
            client = RedisClient()
            result = await client.connect()
            
            assert result is False


class TestRedisClientOperations:
    """Тесты операций Redis."""

    @pytest.mark.asyncio
    async def test_get_hit(self, mock_redis):
        """Тест получения значения (hit)."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.get = AsyncMock(return_value='{"key": "value"}')
        client._connected = True
        
        result = await client.get("test_key")
        
        assert result == {"key": "value"}
        assert client._stats["hits"] == 1

    @pytest.mark.asyncio
    async def test_get_miss(self, mock_redis):
        """Тест получения значения (miss)."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.get = AsyncMock(return_value=None)
        client._connected = True
        
        result = await client.get("test_key")
        
        assert result is None
        assert client._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_plain_string(self, mock_redis):
        """Тест получения строки (не JSON)."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.get = AsyncMock(return_value="plain_text")
        client._connected = True
        
        result = await client.get("test_key")
        
        assert result == "plain_text"

    @pytest.mark.asyncio
    async def test_set_with_expire(self, mock_redis):
        """Тест установки с TTL."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.setex = AsyncMock(return_value=True)
        client._connected = True
        
        result = await client.set("test_key", {"data": "value"}, expire=300)
        
        assert result is True
        assert client._stats["sets"] == 1
        client._client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_without_expire(self, mock_redis):
        """Тест установки без TTL."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.set = AsyncMock(return_value=True)
        client._connected = True
        
        result = await client.set("test_key", "value")
        
        assert result is True
        client._client.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(self, mock_redis):
        """Тест удаления."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.delete = AsyncMock(return_value=1)
        client._connected = True
        
        result = await client.delete("test_key")
        
        assert result is True
        assert client._stats["deletes"] == 1

    @pytest.mark.asyncio
    async def test_exists(self, mock_redis):
        """Тест существования ключа."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.exists = AsyncMock(return_value=1)
        client._connected = True
        
        result = await client.exists("test_key")
        
        assert result is True

    @pytest.mark.asyncio
    async def test_expire(self, mock_redis):
        """Тест установки TTL."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.expire = AsyncMock(return_value=True)
        client._connected = True
        
        result = await client.expire("test_key", 60)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_incr(self, mock_redis):
        """Тест инкремента."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.incr = AsyncMock(return_value=5)
        client._connected = True
        
        result = await client.incr("counter", 1)
        
        assert result == 5


class TestRedisClientBatchOperations:
    """Тесты пакетных операций."""

    @pytest.mark.asyncio
    async def test_get_many(self, mock_redis):
        """Тест получения нескольких значений."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.mget = AsyncMock(return_value=['{"a": 1}', '{"b": 2}', None])
        client._connected = True
        
        result = await client.get_many(["key1", "key2", "key3"])
        
        assert result["key1"] == {"a": 1}
        assert result["key2"] == {"b": 2}
        assert "key3" not in result
        assert client._stats["hits"] == 2
        assert client._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_set_many(self, mock_redis):
        """Тест установки нескольких значений."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.mset = AsyncMock()
        client._client.expire = AsyncMock()
        client._connected = True
        
        await client.set_many(
            {"key1": "value1", "key2": {"nested": "value"}},
            expire=300
        )
        
        client._client.mset.assert_called_once()
        assert client._stats["sets"] == 2

    @pytest.mark.asyncio
    async def test_clear_pattern(self, mock_redis):
        """Тест очистки по паттерну."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.keys = AsyncMock(return_value=["cache:1", "cache:2", "cache:3"])
        client._client.delete = AsyncMock(return_value=3)
        client._connected = True
        
        result = await client.clear_pattern("cache:*")
        
        assert result == 3
        client._client.keys.assert_called_once_with("cache:*")


class TestRedisClientErrorHandling:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio
    async def test_get_error(self, mock_redis):
        """Тест ошибки при get."""
        from app.core.redis_client import RedisError
        
        client = RedisClient()
        client._client = AsyncMock()
        client._client.get = AsyncMock(side_effect=RedisError("Connection lost"))
        client._connected = True
        
        result = await client.get("test_key")
        
        assert result is None
        assert client._stats["errors"] == 1

    @pytest.mark.asyncio
    async def test_set_error(self, mock_redis):
        """Тест ошибки при set."""
        from app.core.redis_client import RedisError
        
        client = RedisClient()
        client._client = AsyncMock()
        client._client.set = AsyncMock(side_effect=RedisError("Connection lost"))
        client._connected = True
        
        result = await client.set("test_key", "value")
        
        assert result is False
        assert client._stats["errors"] == 1


class TestRedisClientStats:
    """Тесты статистики."""

    def test_get_stats(self):
        """Тест получения статистики."""
        client = RedisClient()
        client._stats = {
            "hits": 80,
            "misses": 20,
            "errors": 0,
            "sets": 50,
            "deletes": 10,
        }
        
        stats = client.get_stats()
        
        assert stats["total_requests"] == 100
        assert stats["hit_rate_percent"] == 80.0
        assert stats["connected"] is False

    def test_get_stats_zero_requests(self):
        """Тест статистики без запросов."""
        client = RedisClient()
        
        stats = client.get_stats()
        
        assert stats["hit_rate_percent"] == 0

    def test_is_connected(self):
        """Тест свойства is_connected."""
        client = RedisClient()
        client._connected = True
        
        assert client.is_connected is True
        
        client._connected = False
        assert client.is_connected is False


class TestRedisClientIntegration:
    """Интеграционные тесты (с mock)."""

    @pytest.mark.asyncio
    async def test_cache_workflow(self, mock_redis):
        """Тест рабочего процесса кэширования."""
        client = RedisClient()
        client._client = AsyncMock()
        client._client.get = AsyncMock(return_value=None)  # Cache miss
        client._client.setex = AsyncMock(return_value=True)
        client._connected = True
        
        # Первый запрос (miss)
        result = await client.get("user:1")
        assert result is None
        
        # Запись в кэш
        await client.set("user:1", {"id": 1, "name": "John"}, expire=300)
        
        # Второй запрос (теперь hit)
        client._client.get = AsyncMock(return_value='{"id": 1, "name": "John"}')
        result = await client.get("user:1")
        assert result == {"id": 1, "name": "John"}
        
        # Проверяем статистику
        stats = client.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
