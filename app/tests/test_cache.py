import pytest
import asyncio
import pickle
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.cache import CacheManager, cache, get_cache_key

@pytest.fixture
def cache_manager():
    """Фикстура для менеджера кэша."""
    return CacheManager()

@pytest.mark.asyncio
async def test_cache_manager_connect_disconnect(cache_manager):
    """Тест подключения и отключения от Redis."""
    with patch('app.services.cache.redis.from_url') as mock_redis:
        mock_client = AsyncMock()
        mock_redis.return_value = mock_client
        
        # Тест подключения
        await cache_manager.connect()
        mock_redis.assert_called_once()
        mock_client.ping.assert_called_once()
        
        # Тест отключения
        await cache_manager.disconnect()
        mock_client.close.assert_called_once()

@pytest.mark.asyncio
async def test_cache_manager_get_set(cache_manager):
    """Тест получения и установки значений в кэш."""
    with patch('app.services.cache.redis.from_url') as mock_redis:
        mock_client = AsyncMock()
        mock_redis.return_value = mock_client
        
        await cache_manager.connect()
        
        # Тест установки значения
        mock_client.setex.return_value = True
        result = await cache_manager.set("test_key", "test_value", 300)
        assert result is True
        mock_client.setex.assert_called_once()
        
        # Тест получения значения
        # Сериализуем значение так же, как это делает cache_manager
        serialized_value = pickle.dumps("test_value")
        mock_client.get.return_value = serialized_value
        result = await cache_manager.get("test_key")
        assert result == "test_value"

@pytest.mark.asyncio
async def test_cache_manager_delete(cache_manager):
    """Тест удаления значения из кэша."""
    with patch('app.services.cache.redis.from_url') as mock_redis:
        mock_client = AsyncMock()
        mock_redis.return_value = mock_client
        
        await cache_manager.connect()
        
        # Тест удаления значения
        mock_client.delete.return_value = 1
        result = await cache_manager.delete("test_key")
        assert result is True

@pytest.mark.asyncio
async def test_cache_manager_clear_pattern(cache_manager):
    """Тест очистки кэша по паттерну."""
    with patch('app.services.cache.redis.from_url') as mock_redis:
        mock_client = AsyncMock()
        mock_redis.return_value = mock_client
        
        await cache_manager.connect()
        
        # Тест очистки по паттерну
        mock_client.keys.return_value = ["key1", "key2"]
        mock_client.delete.return_value = 2
        result = await cache_manager.clear_pattern("test:*")
        assert result == 2

def test_get_cache_key():
    """Тест генерации ключа кэша."""
    key1 = get_cache_key("test_func", (1, 2), {"a": 3})
    key2 = get_cache_key("test_func", (1, 2), {"a": 3})
    key3 = get_cache_key("test_func", (2, 1), {"a": 3})
    
    # Одинаковые параметры должны давать одинаковый ключ
    assert key1 == key2
    
    # Разные параметры должны давать разные ключи
    assert key1 != key3

@pytest.mark.asyncio
async def test_cache_decorator():
    """Тест декоратора кэширования."""
    # Создаем тестовую функцию с декоратором кэша
    @cache(expire=60)
    async def test_function(x, y):
        return x + y
    
    # Патчим cache_manager напрямую в модуле
    with patch('app.services.cache.cache_manager') as mock_cache_manager:
        # Настраиваем mock так, чтобы get возвращал None (кэш промах)
        mock_cache_manager.get = AsyncMock(return_value=None)
        mock_cache_manager.set = AsyncMock(return_value=True)
        
        # Вызываем функцию
        result = await test_function(2, 3)
        
        # Проверяем результат
        assert result == 5
        
        # Проверяем, что методы кэша были вызваны
        mock_cache_manager.get.assert_called_once()
        mock_cache_manager.set.assert_called_once()

@pytest.mark.asyncio
async def test_cache_decorator_cache_hit():
    """Тест попадания в кэш."""
    # Создаем тестовую функцию с декоратором кэша
    @cache(expire=60)
    async def test_function(x, y):
        return x + y
    
    # Патчим cache_manager напрямую в модуле
    with patch('app.services.cache.cache_manager') as mock_cache_manager:
        # Настраиваем mock так, чтобы get возвращал закэшированное значение
        mock_cache_manager.get = AsyncMock(return_value=5)
        
        # Вызываем функцию
        result = await test_function(2, 3)
        
        # Проверяем результат
        assert result == 5
        
        # Проверяем, что метод получения из кэша был вызван
        mock_cache_manager.get.assert_called_once()
        
        # Проверяем, что установка в кэш не была вызвана (так как было попадание)
        mock_cache_manager.set.assert_not_called()