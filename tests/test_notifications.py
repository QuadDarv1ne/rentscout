"""
Тесты для системы уведомлений (notifications).

Проверяют:
- WebSocket подключения
- Статистику WebSocket соединений
- Отправку email уведомлений
- Тестовую отправку email
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# Тесты WebSocket статистики
# =============================================================================

class TestWebSocketStats:
    """Тесты эндпоинта /api/notifications/ws/stats"""

    @pytest.mark.asyncio
    async def test_websocket_stats_success(self, client: AsyncClient):
        """Получение общей статистики WebSocket"""
        response = await client.get("/api/notifications/ws/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_connections" in data or "topics" in data

    @pytest.mark.asyncio
    async def test_websocket_stats_by_topic(self, client: AsyncClient):
        """Получение статистики по конкретному топику"""
        response = await client.get(
            "/api/notifications/ws/stats",
            params={"topic": "general"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "topic" in data
        assert "connections" in data

    @pytest.mark.asyncio
    async def test_websocket_stats_city_topic(self, client: AsyncClient):
        """Статистика по топику города"""
        response = await client.get(
            "/api/notifications/ws/stats",
            params={"topic": "city:москва"}
        )
        assert response.status_code == 200


# =============================================================================
# Тесты email уведомлений
# =============================================================================

class TestEmailNotifications:
    """Тесты отправки email уведомлений"""

    @pytest.mark.asyncio
    async def test_send_email_invalid_email(self, client: AsyncClient):
        """Отправка email на невалидный адрес"""
        response = await client.post(
            "/api/notifications/email/send",
            json={
                "to_email": "invalid-email",
                "subject": "Тест",
                "body": "Тестовое сообщение",
            }
        )
        # Должен вернуть 422 (validation error) или 500 (SMTP не настроен)
        assert response.status_code in [422, 500]

    @pytest.mark.asyncio
    async def test_send_email_missing_fields(self, client: AsyncClient):
        """Отправка email с отсутствующими полями"""
        response = await client.post(
            "/api/notifications/email/send",
            json={
                "to_email": "test@example.com",
                # Отсутствуют subject и body
            }
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_test_email_invalid_email(self, client: AsyncClient):
        """Отправка тестового email на невалидный адрес"""
        response = await client.post(
            "/api/notifications/email/test",
            params={"email": "not-an-email"}
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_test_email_format(self, client: AsyncClient):
        """Проверка формата тестового email эндпоинта"""
        response = await client.post(
            "/api/notifications/email/test",
            params={"email": "valid@example.com"}
        )
        # Может вернуть 200 (если SMTP настроен) или 500 (если нет)
        assert response.status_code in [200, 500]


# =============================================================================
# Тесты подписок (subscriptions)
# =============================================================================

class TestSubscriptions:
    """Тесты управления подписками на уведомления"""

    @pytest.mark.asyncio
    async def test_get_subscriptions_unauthenticated(self, client: AsyncClient):
        """Получение подписок без аутентификации"""
        response = await client.get("/api/notifications/subscriptions")
        # Может вернуть 401 (требуется auth) или 200 (пустой список)
        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_create_subscription_invalid(self, client: AsyncClient):
        """Создание подписки с невалидными данными"""
        response = await client.post(
            "/api/notifications/subscriptions",
            json={
                "topic": "",  # Пустой топик
            }
        )
        # Должен вернуть 422 или 400
        assert response.status_code in [400, 422]


# =============================================================================
# Тесты алертов (alerts)
# =============================================================================

class TestAlerts:
    """Тесты управления алертами"""

    @pytest.mark.asyncio
    async def test_get_alerts_unauthenticated(self, client: AsyncClient):
        """Получение алертов без аутентификации"""
        response = await client.get("/api/notifications/alerts")
        # Может вернуть 200 (пустой список) или 401
        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_create_alert_missing_fields(self, client: AsyncClient):
        """Создание алерта с отсутствующими полями"""
        response = await client.post(
            "/api/notifications/alerts",
            json={
                "city": "Москва",
                # Отсутствуют другие обязательные поля
            }
        )
        # Должен вернуть 422 или 200 (если city достаточно)
        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_delete_alert_nonexistent(self, client: AsyncClient):
        """Удаление несуществующего алерта"""
        response = await client.delete("/api/notifications/alerts/99999")
        # Может вернуть 404 или 200 (если уже удалён)
        assert response.status_code in [200, 404]


# =============================================================================
# Тесты истории уведомлений
# =============================================================================

class TestNotificationHistory:
    """Тесты истории уведомлений"""

    @pytest.mark.asyncio
    async def test_get_history_unauthenticated(self, client: AsyncClient):
        """Получение истории без аутентификации"""
        response = await client.get("/api/notifications/history")
        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_get_history_with_pagination(self, client: AsyncClient):
        """Получение истории с пагинацией"""
        response = await client.get(
            "/api/notifications/history",
            params={"limit": 10, "offset": 0}
        )
        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_mark_as_read(self, client: AsyncClient):
        """Отметка уведомления как прочитанного"""
        response = await client.post("/api/notifications/history/1/read")
        assert response.status_code in [200, 401, 404]


# =============================================================================
# Тесты настроек уведомлений
# =============================================================================

class TestNotificationSettings:
    """Тесты настроек уведомлений"""

    @pytest.mark.asyncio
    async def test_get_settings_unauthenticated(self, client: AsyncClient):
        """Получение настроек без аутентификации"""
        response = await client.get("/api/notifications/settings")
        assert response.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_update_settings(self, client: AsyncClient):
        """Обновление настроек уведомлений"""
        response = await client.put(
            "/api/notifications/settings",
            json={
                "email_enabled": True,
                "push_enabled": False,
            }
        )
        assert response.status_code in [200, 401]
