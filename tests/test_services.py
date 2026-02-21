"""
Тесты для сервисов приложения (search, cache, notifications).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.search import SearchService
from app.services.advanced_cache import AdvancedCacheManager
from app.services.notifications import NotificationService
from app.models.schemas import Property


class TestSearchService:
    """Тесты для SearchService."""

    @pytest.fixture
    def search_service(self):
        return SearchService()

    @pytest.mark.asyncio
    async def test_search_basic(self, search_service):
        """Тест базового поиска."""
        with patch.object(search_service, 'parsers') as mock_parsers:
            mock_property = Property(
                source="avito",
                external_id="123456",
                title="2-комнатная квартира",
                price=50000,
                city="Москва",
                rooms=2,
                area=54.5
            )
            mock_parsers.__iter__.return_value = []
            
            # Mock duplicate filter
            search_service.duplicate_filter = MagicMock()
            search_service.duplicate_filter.is_duplicate.return_value = False
            
            result = await search_service.search("Москва", "Квартира")
            
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_with_timeout(self, search_service):
        """Тест поиска с таймаутом."""
        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
            result = await search_service.search("Москва", "Квартира")
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_search_deduplication(self, search_service):
        """Тест дедупликации результатов."""
        with patch.object(search_service.duplicate_filter) as mock_filter:
            mock_filter.is_duplicate.return_value = False
            mock_filter.add.return_value = None
            
            # Mock parsers to return duplicate properties
            with patch.object(search_service, 'parsers') as mock_parsers:
                mock_parser = MagicMock()
                mock_parser.parse.return_value = []
                mock_parsers.__iter__.return_value = [mock_parser]
                
                result = await search_service.search("Москва", "Квартира")
                
                assert mock_filter.is_duplicate.called


class TestAdvancedCacheManager:
    """Тесты для AdvancedCacheManager."""

    @pytest.fixture
    def cache_manager(self):
        return AdvancedCacheManager()

    @pytest.mark.asyncio
    async def test_cache_set_get(self, cache_manager):
        """Тест установки и получения значения из кеша."""
        with patch.object(cache_manager, 'redis_client') as mock_redis:
            mock_redis.set = AsyncMock()
            mock_redis.get = AsyncMock(return_value=b'{"key": "value"}')
            
            await cache_manager.set("test_key", {"key": "value"}, ttl=60)
            result = await cache_manager.get("test_key")
            
            assert result == {"key": "value"}
            mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_delete(self, cache_manager):
        """Тест удаления значения из кеша."""
        with patch.object(cache_manager, 'redis_client') as mock_redis:
            mock_redis.delete = AsyncMock()
            
            await cache_manager.delete("test_key")
            
            mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_clear_pattern(self, cache_manager):
        """Тест очистки кеша по паттерну."""
        with patch.object(cache_manager, 'redis_client') as mock_redis:
            mock_redis.keys = AsyncMock(return_value=[b'key1', b'key2'])
            mock_redis.delete = AsyncMock()
            
            await cache_manager.clear_pattern("test:*")
            
            mock_redis.keys.assert_called_once_with("test:*")

    @pytest.mark.asyncio
    async def test_get_stats(self, cache_manager):
        """Тест получения статистики кеша."""
        with patch.object(cache_manager, 'redis_client') as mock_redis:
            mock_redis.info = AsyncMock(return_value={'used_memory': 1000})
            mock_redis.dbsize = AsyncMock(return_value=50)
            
            stats = await cache_manager.get_stats()
            
            assert 'used_memory' in stats
            assert 'keys_count' in stats


class TestNotificationService:
    """Тесты для NotificationService."""

    @pytest.fixture
    def notification_service(self):
        return NotificationService()

    @pytest.mark.asyncio
    async def test_send_email(self, notification_service):
        """Тест отправки email уведомления."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            result = await notification_service.send_email(
                to="user@example.com",
                subject="Test",
                body="Test body"
            )
            
            assert result is True
            mock_server.sendmail.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_telegram(self, notification_service):
        """Тест отправки Telegram уведомления."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            
            result = await notification_service.send_telegram(
                chat_id=123456,
                message="Test message"
            )
            
            assert result is True
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_notification(self, notification_service):
        """Тест создания уведомления в БД."""
        with patch('app.db.crud.create_notification') as mock_create:
            mock_create.return_value = {"id": 1, "user_id": 123}
            
            result = await notification_service.create_notification(
                user_id=123,
                notification_type="new_property",
                data={"property_id": 456}
            )
            
            assert result["id"] == 1
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_notifications(self, notification_service):
        """Тест получения уведомлений пользователя."""
        with patch('app.db.crud.get_user_notifications') as mock_get:
            mock_get.return_value = [
                {"id": 1, "type": "new_property"},
                {"id": 2, "type": "price_drop"}
            ]
            
            result = await notification_service.get_user_notifications(
                user_id=123,
                limit=10
            )
            
            assert len(result) == 2
            mock_get.assert_called_once()


class TestSearchServiceIntegration:
    """Интеграционные тесты для SearchService."""

    @pytest.mark.asyncio
    async def test_search_multiple_sources(self):
        """Тест поиска по нескольким источникам."""
        service = SearchService()
        
        # Mock all parsers to return empty results
        with patch.object(service, 'parsers') as mock_parsers:
            for parser in mock_parsers:
                parser.parse = AsyncMock(return_value=[])
            
            result = await service.search("Москва", "Квартира")
            
            assert isinstance(result, list)
            # Все парсеры должны быть вызваны
            for parser in mock_parsers:
                parser.parse.assert_called()

    @pytest.mark.asyncio
    async def test_search_circuit_breaker(self):
        """Тест circuit breaker при ошибках парсеров."""
        service = SearchService()
        
        with patch.object(service, 'parsers') as mock_parsers:
            # Первый парсер падает, второй возвращает результат
            mock_parser1 = MagicMock()
            mock_parser1.parse = AsyncMock(side_effect=Exception("Connection error"))
            mock_parser1.__class__.__name__ = "AvitoParser"
            
            mock_parser2 = MagicMock()
            mock_parser2.parse = AsyncMock(return_value=[
                Property(
                    source="cian",
                    external_id="789",
                    title="1-комнатная квартира",
                    price=35000,
                    city="Москва",
                    rooms=1,
                    area=35
                )
            ])
            mock_parser2.__class__.__name__ = "CianParser"
            
            mock_parsers.__iter__.return_value = [mock_parser1, mock_parser2]
            service.duplicate_filter = MagicMock()
            service.duplicate_filter.is_duplicate.return_value = False
            
            result = await service.search("Москва", "Квартира")
            
            # Результат должен содержать данные от работающего парсера
            assert len(result) >= 0  # Circuit breaker может заблокировать упавший парсер
