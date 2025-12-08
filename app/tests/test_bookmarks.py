"""
Тесты для функции закладок и избранного.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.models.bookmarks import BookmarkType, BookmarkService


client = TestClient(app)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def bookmark_service_instance():
    """Создать экземпляр BookmarkService для тестов."""
    return BookmarkService()


@pytest.fixture
def sample_bookmark_data():
    """Стандартные данные для закладки."""
    return {
        "external_property_id": "avito_12345",
        "property_title": "2-комнатная квартира в центре",
        "property_source": "avito",
        "property_price": 50000,
        "property_city": "Москва",
        "property_link": "https://avito.ru/moskva/kvartiry/..."
    }


# ============================================================================
# Тесты BookmarkService
# ============================================================================

@pytest.mark.asyncio
async def test_add_favorite(bookmark_service_instance, sample_bookmark_data):
    """Тест добавления объявления в избранное."""
    bookmark = await bookmark_service_instance.add_favorite(
        user_id="user123",
        **sample_bookmark_data
    )
    
    assert bookmark is not None
    assert bookmark.external_property_id == "avito_12345"
    assert bookmark.bookmark_type == BookmarkType.FAVORITE.value
    assert bookmark.user_id == "user123"


@pytest.mark.asyncio
async def test_add_bookmark(bookmark_service_instance, sample_bookmark_data):
    """Тест добавления в коллекцию закладок."""
    bookmark = await bookmark_service_instance.add_bookmark(
        user_id="user123",
        collection_name="Для сравнения",
        **sample_bookmark_data
    )
    
    assert bookmark is not None
    assert bookmark.bookmark_type == BookmarkType.BOOKMARK.value
    assert bookmark.collection_name == "Для сравнения"


@pytest.mark.asyncio
async def test_record_view(bookmark_service_instance, sample_bookmark_data):
    """Тест записи просмотра объявления."""
    bookmark = await bookmark_service_instance.record_view(
        user_id="user123",
        **sample_bookmark_data
    )
    
    assert bookmark is not None
    assert bookmark.bookmark_type == BookmarkType.VIEWED.value
    assert bookmark.last_viewed_at is not None


@pytest.mark.asyncio
async def test_remove_bookmark(bookmark_service_instance):
    """Тест удаления закладки."""
    result = await bookmark_service_instance.remove_bookmark(
        user_id="user123",
        external_property_id="avito_12345",
        bookmark_type=BookmarkType.FAVORITE.value
    )
    
    assert result is True


@pytest.mark.asyncio
async def test_get_favorites(bookmark_service_instance):
    """Тест получения избранного."""
    favorites = await bookmark_service_instance.get_favorites(
        user_id="user123",
        skip=0,
        limit=50
    )
    
    assert isinstance(favorites, list)


@pytest.mark.asyncio
async def test_get_bookmarks(bookmark_service_instance):
    """Тест получения закладок."""
    bookmarks = await bookmark_service_instance.get_bookmarks(
        user_id="user123",
        collection_name=None,
        skip=0,
        limit=50
    )
    
    assert isinstance(bookmarks, list)


@pytest.mark.asyncio
async def test_get_collections(bookmark_service_instance):
    """Тест получения списка коллекций."""
    collections = await bookmark_service_instance.get_collections(
        user_id="user123"
    )
    
    assert isinstance(collections, list)


@pytest.mark.asyncio
async def test_get_viewed_history(bookmark_service_instance):
    """Тест получения истории просмотров."""
    history = await bookmark_service_instance.get_viewed_history(
        user_id="user123",
        days=30,
        limit=100
    )
    
    assert isinstance(history, list)


@pytest.mark.asyncio
async def test_get_bookmark_stats(bookmark_service_instance):
    """Тест получения статистики закладок."""
    stats = await bookmark_service_instance.get_bookmark_stats(
        user_id="user123"
    )
    
    assert isinstance(stats, dict)
    assert "total_favorites" in stats
    assert "total_bookmarks" in stats
    assert "total_viewed" in stats


@pytest.mark.asyncio
async def test_get_recommendations(bookmark_service_instance):
    """Тест получения рекомендаций."""
    recommendations = await bookmark_service_instance.get_recommendations(
        user_id="user123",
        limit=10
    )
    
    assert isinstance(recommendations, list)


# ============================================================================
# Тесты API Endpoints
# ============================================================================

def test_add_bookmark_endpoint(sample_bookmark_data):
    """Тест endpoint добавления закладки."""
    response = client.post(
        "/api/bookmarks/add?user_id=user123",
        json={
            **sample_bookmark_data,
            "bookmark_type": BookmarkType.FAVORITE.value,
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["external_property_id"] == "avito_12345"
    assert data["bookmark_type"] == BookmarkType.FAVORITE.value


def test_add_bookmark_with_collection(sample_bookmark_data):
    """Тест добавления в коллекцию."""
    response = client.post(
        "/api/bookmarks/add?user_id=user123",
        json={
            **sample_bookmark_data,
            "bookmark_type": BookmarkType.BOOKMARK.value,
            "collection_name": "Мои избранные"
        }
    )
    
    assert response.status_code == 200


def test_add_bookmark_missing_collection():
    """Тест ошибки при отсутствии названия коллекции."""
    response = client.post(
        "/api/bookmarks/add?user_id=user123",
        json={
            "external_property_id": "test_id",
            "property_title": "Test",
            "property_source": "avito",
            "property_price": 50000,
            "property_city": "Москва",
            "property_link": "http://test.com",
            "bookmark_type": BookmarkType.BOOKMARK.value,
        }
    )
    
    assert response.status_code == 400
    assert "collection_name required" in response.json()["detail"]


def test_get_favorites_endpoint():
    """Тест получения избранного через API."""
    response = client.get(
        "/api/bookmarks/favorites?user_id=user123"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "items" in data
    assert "skip" in data
    assert "limit" in data


def test_get_favorites_with_city_filter():
    """Тест фильтрации избранного по городу."""
    response = client.get(
        "/api/bookmarks/favorites?user_id=user123&city=Москва"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 0


def test_get_bookmarks_endpoint():
    """Тест получения закладок через API."""
    response = client.get(
        "/api/bookmarks/bookmarks?user_id=user123"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "items" in data


def test_get_bookmarks_by_collection():
    """Тест получения закладок конкретной коллекции."""
    response = client.get(
        "/api/bookmarks/bookmarks?user_id=user123&collection=Мои избранные"
    )
    
    assert response.status_code == 200


def test_get_collections_endpoint():
    """Тест получения списка коллекций."""
    response = client.get(
        "/api/bookmarks/collections?user_id=user123"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "collections" in data
    assert isinstance(data["collections"], list)


def test_get_view_history_endpoint():
    """Тест получения истории просмотров."""
    response = client.get(
        "/api/bookmarks/history?user_id=user123"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "period_days" in data
    assert "items" in data


def test_get_view_history_custom_period():
    """Тест истории с пользовательским периодом."""
    response = client.get(
        "/api/bookmarks/history?user_id=user123&days=7&limit=50"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["period_days"] == 7


def test_update_bookmark_endpoint():
    """Тест обновления закладки."""
    response = client.put(
        "/api/bookmarks/update/avito_12345?user_id=user123",
        json={
            "notes": "Хороший вариант",
            "rating": 4,
            "tags": ["центр", "квартира", "2-комнаты"]
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "updated"


def test_remove_bookmark_endpoint():
    """Тест удаления закладки."""
    response = client.delete(
        "/api/bookmarks/remove?user_id=user123&external_property_id=avito_12345"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "deleted"


def test_get_bookmark_stats_endpoint():
    """Тест получения статистики."""
    response = client.get(
        "/api/bookmarks/stats?user_id=user123"
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert "total_favorites" in data
    assert "total_bookmarks" in data
    assert "total_viewed" in data
    assert "favorite_cities" in data
    assert "favorite_sources" in data


def test_get_recommendations_endpoint():
    """Тест получения рекомендаций."""
    response = client.get(
        "/api/bookmarks/recommendations?user_id=user123"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_recommendations_with_limit():
    """Тест получения рекомендаций с лимитом."""
    response = client.get(
        "/api/bookmarks/recommendations?user_id=user123&limit=20"
    )
    
    assert response.status_code == 200


def test_add_to_compare_endpoint():
    """Тест добавления для сравнения."""
    response = client.post(
        "/api/bookmarks/compare?user_id=user123&external_property_id=avito_12345"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "added_for_comparison"


def test_get_compare_list_endpoint():
    """Тест получения списка для сравнения."""
    response = client.get(
        "/api/bookmarks/compare?user_id=user123"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "items" in data


def test_clear_compare_list_endpoint():
    """Тест очистки списка для сравнения."""
    response = client.post(
        "/api/bookmarks/compare/clear?user_id=user123"
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cleared"


def test_bookmarks_health_endpoint():
    """Тест health check для сервиса закладок."""
    response = client.get(
        "/api/bookmarks/health"
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert data["service"] == "bookmarks"
    assert "features" in data
    assert len(data["features"]) > 0


# ============================================================================
# Интеграционные тесты
# ============================================================================

def test_full_bookmark_workflow(sample_bookmark_data):
    """Тест полного цикла работы с закладками."""
    user_id = "test_user_123"
    
    # 1. Добавляем в избранное
    response = client.post(
        f"/api/bookmarks/add?user_id={user_id}",
        json={
            **sample_bookmark_data,
            "bookmark_type": BookmarkType.FAVORITE.value,
        }
    )
    assert response.status_code == 200
    
    # 2. Получаем список избранного
    response = client.get(f"/api/bookmarks/favorites?user_id={user_id}")
    assert response.status_code == 200
    
    # 3. Получаем статистику
    response = client.get(f"/api/bookmarks/stats?user_id={user_id}")
    assert response.status_code == 200
    
    # 4. Добавляем в коллекцию
    response = client.post(
        f"/api/bookmarks/add?user_id={user_id}",
        json={
            **sample_bookmark_data,
            "bookmark_type": BookmarkType.BOOKMARK.value,
            "collection_name": "Для анализа"
        }
    )
    assert response.status_code == 200
    
    # 5. Получаем список коллекций
    response = client.get(f"/api/bookmarks/collections?user_id={user_id}")
    assert response.status_code == 200
    
    # 6. Удаляем закладку
    response = client.delete(
        f"/api/bookmarks/remove?user_id={user_id}&external_property_id={sample_bookmark_data['external_property_id']}"
    )
    assert response.status_code == 200
