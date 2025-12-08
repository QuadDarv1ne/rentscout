"""
WebSocket и REST endpoints для системы уведомлений.
"""

from typing import Optional, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, Body
from pydantic import EmailStr

from app.services.notifications import notification_service, EmailNotification
from app.utils.logger import logger
from app.utils.metrics import metrics_collector


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    topic: str = Query("general", description="Топик подписки")
):
    """
    WebSocket endpoint для получения уведомлений в реальном времени.
    
    **Топики:**
    - `general` - все уведомления
    - `city:{название}` - уведомления для конкретного города (например, city:москва)
    - `price_changes` - изменения цен
    - `alerts` - срабатывания алертов
    
    **События:**
    - `new_property` - новое объявление
    - `price_change` - изменение цены
    - `alert_triggered` - сработал алерт
    """
    await notification_service.ws_manager.connect(websocket, topic)
    
    try:
        # Отправляем приветственное сообщение
        await notification_service.ws_manager.send_personal_message(
            f"✅ Connected to topic: {topic}",
            websocket
        )
        
        # Держим соединение открытым
        while True:
            # Ожидаем сообщения от клиента (ping/pong для keep-alive)
            data = await websocket.receive_text()
            
            if data == "ping":
                await websocket.send_text("pong")
            else:
                # Можно обрабатывать команды от клиента
                logger.debug(f"Received from WebSocket: {data}")
                
    except WebSocketDisconnect:
        notification_service.ws_manager.disconnect(websocket, topic)
        logger.info(f"WebSocket client disconnected from {topic}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        notification_service.ws_manager.disconnect(websocket, topic)


@router.get("/ws/stats")
async def get_websocket_stats(topic: Optional[str] = None):
    """
    Получить статистику WebSocket соединений.
    
    **Параметры:**
    - `topic` - конкретный топик (опционально)
    
    **Возвращает:**
    - Количество активных соединений
    - Список топиков
    """
    if topic:
        count = notification_service.ws_manager.get_connection_count(topic)
        return {
            "topic": topic,
            "connections": count
        }
    
    stats = {
        "total_connections": notification_service.ws_manager.get_connection_count(),
        "topics": {
            topic: len(connections)
            for topic, connections in notification_service.ws_manager.active_connections.items()
        }
    }
    
    return stats


@router.post("/email/send")
async def send_email_notification(
    notification: EmailNotification = Body(..., description="Данные email уведомления")
):
    """
    Отправить email уведомление.
    
    **Требования:**
    - Должны быть настроены SMTP параметры в конфигурации
    - Валидный email получателя
    
    **Пример:**
    ```json
    {
        "to_email": "user@example.com",
        "subject": "Тестовое уведомление",
        "body": "Это тестовое сообщение",
        "html_body": "<h1>Это тестовое сообщение</h1>"
    }
    ```
    """
    success = await notification_service.send_email(notification)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Check SMTP configuration."
        )
    
    return {
        "status": "sent",
        "to": notification.to_email,
        "subject": notification.subject
    }


@router.post("/email/test")
async def send_test_email(
    email: EmailStr = Query(..., description="Email для тестовой отправки")
):
    """
    Отправить тестовое email уведомление.
    
    Используется для проверки настроек SMTP.
    """
    notification = EmailNotification(
        to_email=email,
        subject="🧪 Тестовое уведомление RentScout",
        body="Это тестовое письмо для проверки настроек SMTP. Если вы получили его, значит всё работает!",
        html_body="""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>🧪 Тестовое уведомление</h2>
            <p>Это тестовое письмо для проверки настроек SMTP.</p>
            <p style="color: green;"><b>✅ Если вы получили его, значит всё работает!</b></p>
            <hr>
            <p><small>Отправлено с RentScout</small></p>
        </body>
        </html>
        """
    )
    
    success = await notification_service.send_email(notification)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to send test email. Check SMTP configuration in settings."
        )
    
    return {
        "status": "sent",
        "message": f"Test email sent to {email}"
    }


@router.get("/health")
async def check_notification_health():
    """
    Проверить статус сервиса уведомлений.
    
    **Возвращает:**
    - Статус WebSocket менеджера
    - Статус SMTP (настроен/не настроен)
    - Количество активных соединений
    """
    smtp_configured = notification_service._is_email_configured()
    ws_connections = notification_service.ws_manager.get_connection_count()
    
    return {
        "status": "healthy",
        "websocket": {
            "enabled": True,
            "connections": ws_connections,
            "topics": list(notification_service.ws_manager.active_connections.keys())
        },
        "email": {
            "enabled": smtp_configured,
            "smtp_host": notification_service._smtp_config["host"] if smtp_configured else None
        }
    }
