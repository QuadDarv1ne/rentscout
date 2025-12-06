"""Тесты для расширенного кеширования."""

import pytest
import pytest_asyncio
import asyncio
from typing import List

from app.services.advanced_cache import (
    AdvancedCacheManager,
    advanced_cache_manager,
    cached_parser,
    cached,
    get_cache_key,
)
from app.models.schemas import PropertyCreate


@pytest_asyncio.fixture
async def cache_manager():
    """Фикстура для менеджера кеша."""
    manager = AdvancedCacheManager()
    await manager.connect()
    yield manager
    await manager.disconnect()


@pytest.mark.asyncio
async def test_cache_manager_connection(cache_manager):
    """Тест подключения к Redis."""
    assert cache_manager.redis_client is not None


@pytest.mark.asyncio
async def test_cache_set_get(cache_manager):
    """Тест сохранения и получения из кеша."""
    key = "test:key:1"
    value = {"data": "test_value", "count": 42}
    
    # Сохраняем
    result = await cache_manager.set(key, value, expire=60)
    assert result is True
    
    # Получаем
    cached_value = await cache_manager.get(key)
    assert cached_value == value
    assert cache_manager.hits == 1
    
    # Удаляем
    deleted = await cache_manager.delete(key)
    assert deleted is True


@pytest.mark.asyncio
async def test_cache_miss(cache_manager):
    """Тест cache miss."""
    key = "test:nonexistent:key"
    
    value = await cache_manager.get(key)
    assert value is None
    assert cache_manager.misses == 1


@pytest.mark.asyncio
async def test_cache_with_tags(cache_manager):
    """Тест кеширования с тегами."""
    # Сохраняем несколько ключей с общим тегом
    await cache_manager.set("key:1", "value1", expire=60, tags=["city:Москва", "parser"])
    await cache_manager.set("key:2", "value2", expire=60, tags=["city:Москва", "parser"])
    await cache_manager.set("key:3", "value3", expire=60, tags=["city:Казань", "parser"])
    
    # Удаляем по тегу
    deleted = await cache_manager.clear_by_tag("city:Москва")
    assert deleted >= 2
    
    # Проверяем что ключи с тегом удалены
    value1 = await cache_manager.get("key:1")
    value2 = await cache_manager.get("key:2")
    value3 = await cache_manager.get("key:3")
    
    assert value1 is None
    assert value2 is None
    assert value3 == "value3"


@pytest.mark.asyncio
async def test_cache_pattern_clear(cache_manager):
    """Тест удаления по паттерну."""
    # Создаем несколько ключей
    await cache_manager.set("parser:avito:1", "value1", expire=60)
    await cache_manager.set("parser:avito:2", "value2", expire=60)
    await cache_manager.set("parser:cian:1", "value3", expire=60)
    
    # Удаляем по паттерну
    deleted = await cache_manager.clear_pattern("parser:avito:*")
    assert deleted >= 2
    
    # Проверяем
    value1 = await cache_manager.get("parser:avito:1")
    value3 = await cache_manager.get("parser:cian:1")
    
    assert value1 is None
    assert value3 == "value3"


@pytest.mark.asyncio
async def test_cache_stats(cache_manager):
    """Тест получения статистики кеша."""
    # Делаем несколько операций
    await cache_manager.set("key:1", "value1", expire=60)
    await cache_manager.get("key:1")  # hit
    await cache_manager.get("key:nonexistent")  # miss
    
    stats = await cache_manager.get_stats()
    
    assert "hits" in stats
    assert "misses" in stats
    assert "hit_rate" in stats
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1
    assert 0 <= stats["hit_rate"] <= 1


@pytest.mark.asyncio
async def test_get_cache_key():
    """Тест генерации ключей кеша."""
    key1 = get_cache_key("parser:avito", "Москва", property_type="Квартира")
    key2 = get_cache_key("parser:avito", "Москва", property_type="Квартира")
    key3 = get_cache_key("parser:avito", "Казань", property_type="Квартира")
    
    # Одинаковые параметры дают одинаковый ключ
    assert key1 == key2
    
    # Разные параметры дают разные ключи
    assert key1 != key3
    
    # Ключ содержит префикс
    assert key1.startswith("parser:avito:")


@pytest.mark.asyncio
async def test_cached_parser_decorator(cache_manager):
    """Тест декоратора cached_parser."""
    call_count = 0
    
    @cached_parser(expire=60, source="test_parser")
    async def mock_parser(city: str, property_type: str) -> List[PropertyCreate]:
        nonlocal call_count
        call_count += 1
        return [
            PropertyCreate(
                source="test",
                external_id="1",
                title=f"Property in {city}",
                price=5000.0,
                rooms=2,
                area=50.0,
                location=None,
                photos=[],
                description="Test property",
                link=None,
            )
        ]
    
    # Первый вызов - должен выполниться
    result1 = await mock_parser("Москва", "Квартира")
    assert len(result1) == 1
    assert call_count == 1
    
    # Второй вызов - должен вернуться из кеша
    result2 = await mock_parser("Москва", "Квартира")
    assert len(result2) == 1
    assert call_count == 1  # Не увеличился!
    
    # Результаты должны быть одинаковыми
    assert result1[0].title == result2[0].title


@pytest.mark.asyncio
async def test_cached_decorator(cache_manager):
    """Тест универсального декоратора cached."""
    call_count = 0
    
    @cached(expire=60, prefix="test_func")
    async def expensive_function(x: int, y: int) -> int:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)  # Имитируем долгую операцию
        return x + y
    
    # Первый вызов
    result1 = await expensive_function(10, 20)
    assert result1 == 30
    assert call_count == 1
    
    # Второй вызов с теми же параметрами - из кеша
    result2 = await expensive_function(10, 20)
    assert result2 == 30
    assert call_count == 1  # Не увеличился!
    
    # Вызов с другими параметрами
    result3 = await expensive_function(5, 15)
    assert result3 == 20
    assert call_count == 2  # Увеличился!


@pytest.mark.asyncio
async def test_cache_warming(cache_manager):
    """Тест cache warming."""
    warmed_cities = []
    
    async def mock_search(city: str, property_type: str = "Квартира"):
        warmed_cities.append(city)
        return []
    
    # Запускаем warming для 3 городов
    await cache_manager.warm_cache(mock_search, cities=["Москва", "Казань", "Сочи"])
    
    # Проверяем что все города обработаны
    assert len(warmed_cities) == 3
    assert "Москва" in warmed_cities
    assert "Казань" in warmed_cities
    assert "Сочи" in warmed_cities


@pytest.mark.asyncio
async def test_cache_expiration(cache_manager):
    """Тест истечения срока кеша."""
    key = "test:expiring:key"
    value = "test_value"
    
    # Сохраняем с очень коротким TTL
    await cache_manager.set(key, value, expire=1)
    
    # Сразу получаем - должно быть в кеше
    cached = await cache_manager.get(key)
    assert cached == value
    
    # Ждем истечения
    await asyncio.sleep(1.5)
    
    # Теперь должно быть None
    expired = await cache_manager.get(key)
    assert expired is None
