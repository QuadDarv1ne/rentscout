"""
Сервис уведомлений для RentScout.

Поддерживает:
- WebSocket уведомления в реальном времени
- Email уведомления через SMTP
- Система подписок на обновления
"""

import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Set, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

from fastapi import WebSocket
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.utils.logger import logger
from app.models.schemas import Property


class EmailNotification(BaseModel):
    """Модель email уведомления."""
    to_email: EmailStr
    subject: str
    body: str
    html_body: Optional[str] = None


class WebSocketMessage(BaseModel):
    """Модель WebSocket сообщения."""
    event_type: str  # "new_property", "price_change", "alert_triggered"
    data: Dict[str, Any]
    timestamp: datetime = datetime.now()


@dataclass
class ConnectionManager:
    """Менеджер WebSocket соединений."""
    
    # Активные соединения по темам
    active_connections: Dict[str, Set[WebSocket]] = field(default_factory=dict)
    
    # Подписки пользователей (email -> список тем)
    subscriptions: Dict[str, List[str]] = field(default_factory=dict)
    
    async def connect(self, websocket: WebSocket, topic: str = "general"):
        """Подключить WebSocket клиента к топику."""
        await websocket.accept()
        
        if topic not in self.active_connections:
            self.active_connections[topic] = set()
        
        self.active_connections[topic].add(websocket)
        logger.info(f"WebSocket connected to topic '{topic}'. Total: {len(self.active_connections[topic])}")
    
    def disconnect(self, websocket: WebSocket, topic: str = "general"):
        """Отключить WebSocket клиента от топика."""
        if topic in self.active_connections:
            self.active_connections[topic].discard(websocket)
            logger.info(f"WebSocket disconnected from topic '{topic}'. Remaining: {len(self.active_connections[topic])}")
            
            # Удаляем топик если он пустой
            if not self.active_connections[topic]:
                del self.active_connections[topic]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Отправить персональное сообщение одному клиенту."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
    
    async def broadcast(self, message: WebSocketMessage, topic: str = "general"):
        """Отправить сообщение всем подключенным клиентам топика."""
        if topic not in self.active_connections:
            logger.debug(f"No connections for topic '{topic}'")
            return
        
        # Создаем копию списка соединений для безопасной итерации
        connections = list(self.active_connections[topic])
        disconnected = []
        
        for connection in connections:
            try:
                await connection.send_json(message.model_dump(mode='json'))
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {e}")
                disconnected.append(connection)
        
        # Удаляем разорванные соединения
        for ws in disconnected:
            self.disconnect(ws, topic)
    
    async def broadcast_to_multiple_topics(self, message: WebSocketMessage, topics: List[str]):
        """Отправить сообщение в несколько топиков одновременно."""
        tasks = [self.broadcast(message, topic) for topic in topics]
        await asyncio.gather(*tasks)
    
    def get_connection_count(self, topic: Optional[str] = None) -> int:
        """Получить количество активных соединений."""
        if topic:
            return len(self.active_connections.get(topic, set()))
        return sum(len(conns) for conns in self.active_connections.values())


class NotificationService:
    """Сервис для отправки уведомлений."""
    
    def __init__(self):
        self.ws_manager = ConnectionManager()
        self._smtp_config = {
            "host": getattr(settings, "SMTP_HOST", "smtp.gmail.com"),
            "port": getattr(settings, "SMTP_PORT", 587),
            "username": getattr(settings, "SMTP_USERNAME", None),
            "password": getattr(settings, "SMTP_PASSWORD", None),
            "from_email": getattr(settings, "SMTP_FROM_EMAIL", "noreply@rentscout.com"),
        }
    
    async def notify_new_property(self, property_data: Property, city: str):
        """Уведомить о новом объявлении."""
        message = WebSocketMessage(
            event_type="new_property",
            data={
                "property_id": property_data.external_id,
                "title": property_data.title,
                "price": property_data.price,
                "city": property_data.city,
                "rooms": property_data.rooms,
                "area": property_data.area,
                "link": property_data.link,
            }
        )
        
        # Отправляем в топики города и общий топик
        topics = [f"city:{city.lower()}", "general"]
        await self.ws_manager.broadcast_to_multiple_topics(message, topics)
        
        logger.info(f"Notified about new property: {property_data.title} in {city}")
    
    async def notify_price_change(
        self, 
        property_id: str, 
        old_price: float, 
        new_price: float,
        city: str
    ):
        """Уведомить об изменении цены."""
        price_diff = new_price - old_price
        percentage = (price_diff / old_price) * 100
        
        message = WebSocketMessage(
            event_type="price_change",
            data={
                "property_id": property_id,
                "old_price": old_price,
                "new_price": new_price,
                "difference": price_diff,
                "percentage": round(percentage, 2),
            }
        )
        
        topics = [f"city:{city.lower()}", "price_changes"]
        await self.ws_manager.broadcast_to_multiple_topics(message, topics)
        
        logger.info(f"Notified about price change: {property_id} ({percentage:+.1f}%)")
    
    async def notify_alert_triggered(
        self,
        alert_id: int,
        properties: List[Property],
        email: Optional[str] = None
    ):
        """Уведомить о срабатывании алерта."""
        message = WebSocketMessage(
            event_type="alert_triggered",
            data={
                "alert_id": alert_id,
                "count": len(properties),
                "properties": [
                    {
                        "id": prop.external_id,
                        "title": prop.title,
                        "price": prop.price,
                        "link": prop.link,
                    }
                    for prop in properties[:5]  # Показываем первые 5
                ],
            }
        )
        
        await self.ws_manager.broadcast(message, "alerts")
        
        # Отправляем email если указан
        if email and self._is_email_configured():
            await self.send_alert_email(email, alert_id, properties)
        
        logger.info(f"Alert {alert_id} triggered with {len(properties)} properties")
    
    def _is_email_configured(self) -> bool:
        """Проверить, настроен ли SMTP."""
        return bool(
            self._smtp_config["username"] and 
            self._smtp_config["password"]
        )
    
    async def send_email(self, notification: EmailNotification) -> bool:
        """Отправить email уведомление."""
        if not self._is_email_configured():
            logger.warning("SMTP not configured, skipping email")
            return False
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = notification.subject
            msg["From"] = self._smtp_config["from_email"]
            msg["To"] = notification.to_email
            
            # Текстовая версия
            text_part = MIMEText(notification.body, "plain", "utf-8")
            msg.attach(text_part)
            
            # HTML версия (если есть)
            if notification.html_body:
                html_part = MIMEText(notification.html_body, "html", "utf-8")
                msg.attach(html_part)
            
            # Отправка через SMTP
            with smtplib.SMTP(
                self._smtp_config["host"], 
                self._smtp_config["port"]
            ) as server:
                server.starttls()
                server.login(
                    self._smtp_config["username"],
                    self._smtp_config["password"]
                )
                server.send_message(msg)
            
            logger.info(f"Email sent to {notification.to_email}: {notification.subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    async def send_alert_email(
        self,
        email: str,
        alert_id: int,
        properties: List[Property]
    ):
        """Отправить email с результатами алерта."""
        subject = f"🔔 RentScout: Найдено {len(properties)} новых объявлений"
        
        # Текстовая версия
        body = f"Здравствуйте!\n\n"
        body += f"По вашему алерту #{alert_id} найдено {len(properties)} новых объявлений:\n\n"
        
        for i, prop in enumerate(properties[:10], 1):
            body += f"{i}. {prop.title}\n"
            body += f"   Цена: {prop.price:,.0f} ₽\n"
            body += f"   Площадь: {prop.area} м²\n"
            body += f"   Ссылка: {prop.link}\n\n"
        
        if len(properties) > 10:
            body += f"... и ещё {len(properties) - 10} объявлений\n"
        
        body += "\n---\nС уважением, команда RentScout"
        
        # HTML версия
        html_body = f"""
        <html>
        <body>
            <h2>🔔 Найдено {len(properties)} новых объявлений</h2>
            <p>По вашему алерту <b>#{alert_id}</b>:</p>
            <ul>
        """
        
        for prop in properties[:10]:
            html_body += f"""
                <li>
                    <b>{prop.title}</b><br>
                    Цена: {prop.price:,.0f} ₽ | 
                    Площадь: {prop.area} м²<br>
                    <a href="{prop.link}">Посмотреть объявление</a>
                </li>
            """
        
        if len(properties) > 10:
            html_body += f"<li><i>... и ещё {len(properties) - 10} объявлений</i></li>"
        
        html_body += """
            </ul>
            <hr>
            <p><small>С уважением, команда RentScout</small></p>
        </body>
        </html>
        """
        
        notification = EmailNotification(
            to_email=email,
            subject=subject,
            body=body,
            html_body=html_body
        )
        
        await self.send_email(notification)


# Глобальный экземпляр сервиса
notification_service = NotificationService()
