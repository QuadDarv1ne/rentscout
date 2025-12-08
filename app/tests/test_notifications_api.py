"""
Тесты для API endpoints уведомлений.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.notifications import EmailNotification
from app.models.schemas import PropertyCreate


# Отключаем rate limiting для тестов
@pytest.fixture(autouse=True)
def disable_rate_limit():
    """Отключить rate limiting в тестах."""
    with patch('app.utils.ip_ratelimiter.RateLimitMiddleware.dispatch') as mock_dispatch:
        # Пропускаем все запросы без ограничений
        async def passthrough(request, call_next):
            return await call_next(request)
        
        mock_dispatch.side_effect = passthrough
        yield


client = TestClient(app)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_property():
    """Создать тестовый объект недвижимости."""
    return PropertyCreate(
        source="avito",
        external_id="test123",
        title="Квартира-студия",
        price=35000,
        currency="RUB",
        rooms=1,
        area=30.0,
        city="Санкт-Петербург",
        link="https://example.com/property/test123"
    )


# ============================================================================
# Тесты WebSocket Stats Endpoint
# ============================================================================

def test_get_websocket_stats_no_connections():
    """Тест получения статистики без активных соединений."""
    response = client.get("/api/notifications/ws/stats")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "total_connections" in data
    assert "topics" in data
    assert data["total_connections"] == 0


def test_get_websocket_stats_with_topic():
    """Тест получения статистики для конкретного топика."""
    response = client.get("/api/notifications/ws/stats?topic=general")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "topic" in data
    assert "connections" in data
    assert data["topic"] == "general"


# ============================================================================
# Тесты Email Endpoints
# ============================================================================

@pytest.mark.asyncio
async def test_send_email_notification_success():
    """Тест успешной отправки email уведомления."""
    notification_data = {
        "to_email": "user@example.com",
        "subject": "Тестовое уведомление",
        "body": "Это тестовое сообщение"
    }
    
    with patch(
        'app.services.notifications.notification_service.send_email',
        new_callable=AsyncMock,
        return_value=True
    ):
        response = client.post(
            "/api/notifications/email/send",
            json=notification_data
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "sent"
        assert data["to"] == "user@example.com"
        assert data["subject"] == "Тестовое уведомление"


@pytest.mark.asyncio
async def test_send_email_notification_failure():
    """Тест обработки ошибки отправки email."""
    notification_data = {
        "to_email": "user@example.com",
        "subject": "Test",
        "body": "Test body"
    }
    
    with patch(
        'app.services.notifications.notification_service.send_email',
        new_callable=AsyncMock,
        return_value=False
    ):
        response = client.post(
            "/api/notifications/email/send",
            json=notification_data
        )
        
        assert response.status_code == 500
        assert "Failed to send email" in response.json()["detail"]


def test_send_email_invalid_data():
    """Тест валидации некорректных данных email."""
    invalid_data = {
        "to_email": "invalid-email",  # Невалидный email
        "subject": "Test",
        "body": "Test"
    }
    
    response = client.post(
        "/api/notifications/email/send",
        json=invalid_data
    )
    
    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_send_test_email_success():
    """Тест отправки тестового email."""
    with patch(
        'app.services.notifications.notification_service.send_email',
        new_callable=AsyncMock,
        return_value=True
    ):
        response = client.post(
            "/api/notifications/email/test?email=test@example.com"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "sent"
        assert "test@example.com" in data["message"]


@pytest.mark.asyncio
async def test_send_test_email_failure():
    """Тест обработки ошибки при отправке тестового email."""
    with patch(
        'app.services.notifications.notification_service.send_email',
        new_callable=AsyncMock,
        return_value=False
    ):
        response = client.post(
            "/api/notifications/email/test?email=test@example.com"
        )
        
        assert response.status_code == 500
        assert "Failed to send test email" in response.json()["detail"]


# ============================================================================
# Тесты Health Endpoint
# ============================================================================

def test_notification_health_check():
    """Тест проверки статуса сервиса уведомлений."""
    response = client.get("/api/notifications/health")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "healthy"
    assert "websocket" in data
    assert "email" in data
    
    # WebSocket должен быть включен
    assert data["websocket"]["enabled"] is True
    assert "connections" in data["websocket"]
    assert "topics" in data["websocket"]
    
    # Email может быть не настроен в тестах
    assert "enabled" in data["email"]


def test_notification_health_websocket_info():
    """Тест информации о WebSocket в health check."""
    response = client.get("/api/notifications/health")
    
    assert response.status_code == 200
    data = response.json()
    
    ws_data = data["websocket"]
    assert ws_data["enabled"] is True
    assert isinstance(ws_data["connections"], int)
    assert isinstance(ws_data["topics"], list)


def test_notification_health_email_info():
    """Тест информации о Email в health check."""
    response = client.get("/api/notifications/health")
    
    assert response.status_code == 200
    data = response.json()
    
    email_data = data["email"]
    assert "enabled" in email_data
    
    # Если email настроен, должен быть SMTP host
    if email_data["enabled"]:
        assert "smtp_host" in email_data
        assert email_data["smtp_host"] is not None


# ============================================================================
# Интеграционные тесты
# ============================================================================

@pytest.mark.asyncio
async def test_full_notification_flow(mock_property):
    """Тест полного цикла уведомлений."""
    # 1. Проверяем health
    health_response = client.get("/api/notifications/health")
    assert health_response.status_code == 200
    
    # 2. Получаем статистику WebSocket
    stats_response = client.get("/api/notifications/ws/stats")
    assert stats_response.status_code == 200
    
    # 3. Пытаемся отправить тестовый email
    with patch(
        'app.services.notifications.notification_service.send_email',
        new_callable=AsyncMock,
        return_value=True
    ):
        email_response = client.post(
            "/api/notifications/email/test?email=integration@test.com"
        )
        assert email_response.status_code == 200


@pytest.mark.asyncio
async def test_email_with_html_body():
    """Тест отправки email с HTML содержимым."""
    notification_data = {
        "to_email": "html@example.com",
        "subject": "HTML Email Test",
        "body": "Plain text version",
        "html_body": "<h1>HTML Version</h1><p>This is HTML email</p>"
    }
    
    with patch(
        'app.services.notifications.notification_service.send_email',
        new_callable=AsyncMock,
        return_value=True
    ):
        response = client.post(
            "/api/notifications/email/send",
            json=notification_data
        )
        
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_multiple_email_sends():
    """Тест множественной отправки email."""
    emails = [
        "user1@example.com",
        "user2@example.com",
        "user3@example.com"
    ]
    
    with patch(
        'app.services.notifications.notification_service.send_email',
        new_callable=AsyncMock,
        return_value=True
    ):
        for email in emails:
            notification_data = {
                "to_email": email,
                "subject": f"Test to {email}",
                "body": "Test message"
            }
            
            response = client.post(
                "/api/notifications/email/send",
                json=notification_data
            )
            
            assert response.status_code == 200
            assert response.json()["to"] == email
