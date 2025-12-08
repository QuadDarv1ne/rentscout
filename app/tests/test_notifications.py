"""
Тесты для системы уведомлений RentScout.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import WebSocket
from datetime import datetime

from app.services.notifications import (
    NotificationService,
    ConnectionManager,
    WebSocketMessage,
    EmailNotification,
    notification_service
)
from app.models.schemas import PropertyCreate


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_property():
    """Создать тестовый объект недвижимости."""
    return PropertyCreate(
        source="avito",
        external_id="test123",
        title="2-комнатная квартира в центре",
        price=50000,
        currency="RUB",
        rooms=2,
        area=60.0,
        city="Москва",
        district="Центральный",
        link="https://example.com/property/test123",
        photos=["photo1.jpg", "photo2.jpg"],
        is_verified=True
    )


@pytest.fixture
def connection_manager():
    """Создать новый ConnectionManager для тестов."""
    return ConnectionManager()


@pytest.fixture
def notification_svc():
    """Создать новый NotificationService для тестов."""
    return NotificationService()


# ============================================================================
# Тесты ConnectionManager
# ============================================================================

@pytest.mark.asyncio
async def test_websocket_connect(connection_manager):
    """Тест подключения WebSocket клиента."""
    mock_ws = AsyncMock(spec=WebSocket)
    
    await connection_manager.connect(mock_ws, "test_topic")
    
    assert "test_topic" in connection_manager.active_connections
    assert mock_ws in connection_manager.active_connections["test_topic"]
    assert connection_manager.get_connection_count("test_topic") == 1
    mock_ws.accept.assert_called_once()


@pytest.mark.asyncio
async def test_websocket_disconnect(connection_manager):
    """Тест отключения WebSocket клиента."""
    mock_ws = AsyncMock(spec=WebSocket)
    
    await connection_manager.connect(mock_ws, "test_topic")
    connection_manager.disconnect(mock_ws, "test_topic")
    
    assert connection_manager.get_connection_count("test_topic") == 0
    assert "test_topic" not in connection_manager.active_connections


@pytest.mark.asyncio
async def test_websocket_multiple_connections(connection_manager):
    """Тест множественных подключений."""
    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)
    ws3 = AsyncMock(spec=WebSocket)
    
    await connection_manager.connect(ws1, "topic1")
    await connection_manager.connect(ws2, "topic1")
    await connection_manager.connect(ws3, "topic2")
    
    assert connection_manager.get_connection_count("topic1") == 2
    assert connection_manager.get_connection_count("topic2") == 1
    assert connection_manager.get_connection_count() == 3


@pytest.mark.asyncio
async def test_send_personal_message(connection_manager):
    """Тест отправки персонального сообщения."""
    mock_ws = AsyncMock(spec=WebSocket)
    
    await connection_manager.send_personal_message("test message", mock_ws)
    
    mock_ws.send_text.assert_called_once_with("test message")


@pytest.mark.asyncio
async def test_broadcast_message(connection_manager):
    """Тест широковещательной рассылки."""
    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)
    
    await connection_manager.connect(ws1, "test_topic")
    await connection_manager.connect(ws2, "test_topic")
    
    message = WebSocketMessage(
        event_type="test_event",
        data={"key": "value"},
        timestamp=datetime.now()
    )
    
    await connection_manager.broadcast(message, "test_topic")
    
    assert ws1.send_json.call_count == 1
    assert ws2.send_json.call_count == 1


@pytest.mark.asyncio
async def test_broadcast_to_multiple_topics(connection_manager):
    """Тест рассылки в несколько топиков."""
    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)
    
    await connection_manager.connect(ws1, "topic1")
    await connection_manager.connect(ws2, "topic2")
    
    message = WebSocketMessage(
        event_type="multi_topic_event",
        data={"info": "test"}
    )
    
    await connection_manager.broadcast_to_multiple_topics(message, ["topic1", "topic2"])
    
    assert ws1.send_json.call_count == 1
    assert ws2.send_json.call_count == 1


@pytest.mark.asyncio
async def test_broadcast_removes_disconnected_clients(connection_manager):
    """Тест удаления разорванных соединений при рассылке."""
    ws_good = AsyncMock(spec=WebSocket)
    ws_bad = AsyncMock(spec=WebSocket)
    ws_bad.send_json.side_effect = Exception("Connection lost")
    
    await connection_manager.connect(ws_good, "test_topic")
    await connection_manager.connect(ws_bad, "test_topic")
    
    message = WebSocketMessage(event_type="test", data={})
    
    await connection_manager.broadcast(message, "test_topic")
    
    # Плохое соединение должно быть удалено
    assert connection_manager.get_connection_count("test_topic") == 1
    assert ws_good in connection_manager.active_connections["test_topic"]
    assert ws_bad not in connection_manager.active_connections["test_topic"]


# ============================================================================
# Тесты NotificationService
# ============================================================================

@pytest.mark.asyncio
async def test_notify_new_property(notification_svc, mock_property):
    """Тест уведомления о новом объявлении."""
    with patch.object(
        notification_svc.ws_manager,
        'broadcast_to_multiple_topics',
        new_callable=AsyncMock
    ) as mock_broadcast:
        await notification_svc.notify_new_property(mock_property, "Москва")
        
        mock_broadcast.assert_called_once()
        call_args = mock_broadcast.call_args
        message = call_args[0][0]
        topics = call_args[0][1]
        
        assert message.event_type == "new_property"
        assert message.data["title"] == mock_property.title
        assert message.data["price"] == mock_property.price
        assert "city:москва" in topics
        assert "general" in topics


@pytest.mark.asyncio
async def test_notify_price_change(notification_svc):
    """Тест уведомления об изменении цены."""
    with patch.object(
        notification_svc.ws_manager,
        'broadcast_to_multiple_topics',
        new_callable=AsyncMock
    ) as mock_broadcast:
        await notification_svc.notify_price_change(
            property_id="test123",
            old_price=50000,
            new_price=45000,
            city="Москва"
        )
        
        mock_broadcast.assert_called_once()
        message = mock_broadcast.call_args[0][0]
        
        assert message.event_type == "price_change"
        assert message.data["old_price"] == 50000
        assert message.data["new_price"] == 45000
        assert message.data["difference"] == -5000
        assert message.data["percentage"] == -10.0


@pytest.mark.asyncio
async def test_notify_alert_triggered_without_email(notification_svc, mock_property):
    """Тест уведомления о срабатывании алерта без email."""
    properties = [mock_property]
    
    with patch.object(
        notification_svc.ws_manager,
        'broadcast',
        new_callable=AsyncMock
    ) as mock_broadcast:
        await notification_svc.notify_alert_triggered(
            alert_id=1,
            properties=properties,
            email=None
        )
        
        mock_broadcast.assert_called_once()
        message = mock_broadcast.call_args[0][0]
        
        assert message.event_type == "alert_triggered"
        assert message.data["alert_id"] == 1
        assert message.data["count"] == 1


@pytest.mark.asyncio
async def test_send_email_not_configured(notification_svc):
    """Тест отправки email когда SMTP не настроен."""
    notification = EmailNotification(
        to_email="test@example.com",
        subject="Test",
        body="Test body"
    )
    
    # По умолчанию SMTP не настроен в тестах
    result = await notification_svc.send_email(notification)
    
    assert result is False


@pytest.mark.asyncio
async def test_send_email_success(notification_svc):
    """Тест успешной отправки email."""
    notification = EmailNotification(
        to_email="test@example.com",
        subject="Test Subject",
        body="Test body",
        html_body="<h1>Test</h1>"
    )
    
    # Мокируем SMTP конфигурацию
    notification_svc._smtp_config["username"] = "test@smtp.com"
    notification_svc._smtp_config["password"] = "password"
    
    with patch('smtplib.SMTP') as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        result = await notification_svc.send_email(notification)
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_failure(notification_svc):
    """Тест обработки ошибки отправки email."""
    notification = EmailNotification(
        to_email="test@example.com",
        subject="Test",
        body="Test"
    )
    
    notification_svc._smtp_config["username"] = "test@smtp.com"
    notification_svc._smtp_config["password"] = "password"
    
    with patch('smtplib.SMTP') as mock_smtp:
        mock_smtp.side_effect = Exception("SMTP error")
        
        result = await notification_svc.send_email(notification)
        
        assert result is False


@pytest.mark.asyncio
async def test_send_alert_email_content(notification_svc, mock_property):
    """Тест содержимого email с результатами алерта."""
    properties = [mock_property] * 3
    
    notification_svc._smtp_config["username"] = "test@smtp.com"
    notification_svc._smtp_config["password"] = "password"
    
    with patch('smtplib.SMTP') as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        await notification_svc.send_alert_email(
            email="user@example.com",
            alert_id=42,
            properties=properties
        )
        
        # Проверяем, что send_message был вызван
        assert mock_server.send_message.called
        
        # Получаем объект сообщения
        sent_message = mock_server.send_message.call_args[0][0]
        
        assert "Найдено 3 новых объявлений" in sent_message["Subject"]
        assert sent_message["To"] == "user@example.com"


def test_is_email_configured_false(notification_svc):
    """Тест проверки конфигурации SMTP когда не настроено."""
    notification_svc._smtp_config["username"] = None
    notification_svc._smtp_config["password"] = None
    
    assert notification_svc._is_email_configured() is False


def test_is_email_configured_true(notification_svc):
    """Тест проверки конфигурации SMTP когда настроено."""
    notification_svc._smtp_config["username"] = "test@smtp.com"
    notification_svc._smtp_config["password"] = "password"
    
    assert notification_svc._is_email_configured() is True


# ============================================================================
# Тесты WebSocketMessage модели
# ============================================================================

def test_websocket_message_creation():
    """Тест создания WebSocket сообщения."""
    message = WebSocketMessage(
        event_type="test_event",
        data={"key": "value"}
    )
    
    assert message.event_type == "test_event"
    assert message.data == {"key": "value"}
    assert isinstance(message.timestamp, datetime)


def test_websocket_message_serialization():
    """Тест сериализации WebSocket сообщения."""
    message = WebSocketMessage(
        event_type="new_property",
        data={"property_id": "123", "price": 50000}
    )
    
    json_data = message.model_dump(mode='json')
    
    assert json_data["event_type"] == "new_property"
    assert json_data["data"]["property_id"] == "123"
    assert "timestamp" in json_data


# ============================================================================
# Тесты EmailNotification модели
# ============================================================================

def test_email_notification_creation():
    """Тест создания email уведомления."""
    notification = EmailNotification(
        to_email="user@example.com",
        subject="Test Subject",
        body="Test body"
    )
    
    assert notification.to_email == "user@example.com"
    assert notification.subject == "Test Subject"
    assert notification.body == "Test body"
    assert notification.html_body is None


def test_email_notification_with_html():
    """Тест создания email с HTML."""
    notification = EmailNotification(
        to_email="user@example.com",
        subject="Test",
        body="Plain text",
        html_body="<h1>HTML</h1>"
    )
    
    assert notification.html_body == "<h1>HTML</h1>"


def test_email_notification_invalid_email():
    """Тест валидации некорректного email."""
    with pytest.raises(Exception):  # Pydantic ValidationError
        EmailNotification(
            to_email="invalid-email",
            subject="Test",
            body="Test"
        )
