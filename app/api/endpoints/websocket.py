"""
WebSocket endpoint для real-time уведомлений.

Позволяет клиентам получать уведомления в реальном времени:
- Новые объявления по заданным критериям
- Изменения цен
- Системные уведомления
"""

import asyncio
import json
import time
from typing import Dict, Set, Optional, Any
from datetime import datetime
import logging

from fastapi import WebSocket, WebSocketDisconnect, APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from app.utils.logger import logger
from app.dependencies.auth import get_current_user_optional
from app.db.models.schemas import User

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Connection Manager
# ============================================================================

class ConnectionManager:
    """
    Менеджер WebSocket подключений.

    Управляет:
    - Активными подключениями по user_id
    - Подписками по каналам (channels)
    - Рассылкой уведомлений
    """

    def __init__(self):
        # active_connections[user_id] = Set[WebSocket]
        self.active_connections: Dict[int, Set[WebSocket]] = {}

        # channel_subscriptions[channel] = Set[user_id]
        self.channel_subscriptions: Dict[str, Set[int]] = {}

        # Статистика
        self.total_connections = 0
        self.total_disconnections = 0
        self.messages_sent = 0

    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
        channels: Optional[list] = None
    ) -> None:
        """
        Принять WebSocket подключение.

        Args:
            websocket: WebSocket соединение
            user_id: ID пользователя
            channels: Каналы для подписки
        """
        await websocket.accept()

        # Добавляем подключение
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)

        # Подписываем на каналы
        if channels:
            for channel in channels:
                if channel not in self.channel_subscriptions:
                    self.channel_subscriptions[channel] = set()
                self.channel_subscriptions[channel].add(user_id)

        self.total_connections += 1

        logger.info(
            f"WebSocket connected: user_id={user_id}, "
            f"channels={channels}, "
            f"total_active={len(self.active_connections)}"
        )

        # Отправляем приветственное сообщение
        await self.send_personal_message(
            websocket,
            {
                "type": "connected",
                "user_id": user_id,
                "channels": channels,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def disconnect(
        self,
        websocket: WebSocket,
        user_id: int,
        channels: Optional[list] = None
    ) -> None:
        """
        Отключить WebSocket.

        Args:
            websocket: WebSocket соединение
            user_id: ID пользователя
            channels: Каналы для отписки
        """
        # Удаляем подключение
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

        # Отписываем от каналов
        if channels:
            for channel in self.channel_subscriptions:
                self.channel_subscriptions[channel].discard(user_id)

        self.total_disconnections += 1

        logger.info(
            f"WebSocket disconnected: user_id={user_id}, "
            f"total_active={len(self.active_connections)}"
        )

    async def send_personal_message(
        self,
        websocket: WebSocket,
        message: Dict[str, Any]
    ) -> bool:
        """
        Отправить сообщение конкретному подключению.

        Args:
            websocket: WebSocket соединение
            message: Сообщение

        Returns:
            True если успешно
        """
        try:
            await websocket.send_json(message)
            self.messages_sent += 1
            return True
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            return False

    async def broadcast_to_user(
        self,
        user_id: int,
        message: Dict[str, Any]
    ) -> int:
        """
        Отправить сообщение всем подключениям пользователя.

        Args:
            user_id: ID пользователя
            message: Сообщение

        Returns:
            Количество успешных отправок
        """
        if user_id not in self.active_connections:
            return 0

        sent_count = 0
        disconnected = []

        for websocket in self.active_connections[user_id]:
            if await self.send_personal_message(websocket, message):
                sent_count += 1
            else:
                disconnected.append(websocket)

        # Удаляем отключившиеся
        for websocket in disconnected:
            self.active_connections[user_id].discard(websocket)

        return sent_count

    async def broadcast_to_channel(
        self,
        channel: str,
        message: Dict[str, Any]
    ) -> int:
        """
        Отправить сообщение всем подписчикам канала.

        Args:
            channel: Название канала
            message: Сообщение

        Returns:
            Количество успешных отправок
        """
        if channel not in self.channel_subscriptions:
            return 0

        sent_count = 0
        for user_id in self.channel_subscriptions[channel]:
            sent_count += await self.broadcast_to_user(user_id, message)

        return sent_count

    async def broadcast_all(
        self,
        message: Dict[str, Any]
    ) -> int:
        """
        Отправить сообщение всем подключениям.

        Args:
            message: Сообщение

        Returns:
            Количество успешных отправок
        """
        sent_count = 0
        for user_id in self.active_connections:
            sent_count += await self.broadcast_to_user(user_id, message)
        return sent_count

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику подключений."""
        return {
            "active_users": len(self.active_connections),
            "total_connections": self.total_connections,
            "total_disconnections": self.total_disconnections,
            "active_channels": len(self.channel_subscriptions),
            "messages_sent": self.messages_sent,
            "channels": {
                channel: len(users)
                for channel, users in self.channel_subscriptions.items()
            }
        }


# Глобальный менеджер
manager = ConnectionManager()


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@router.websocket("/ws/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    channels: str = Query(
        default="",
        description="Каналы для подписки (comma-separated)"
    ),
    token: Optional[str] = Query(default=None)
):
    """
    WebSocket endpoint для real-time уведомлений.

    Подключение:
        ws://localhost:8000/ws/notifications?channels=new_properties,price_drops

    Каналы:
        - new_properties: Новые объявления
        - price_drops: Снижение цен
        - alerts: Оповещения
        - system: Системные уведомления

    Формат сообщений:
        {
            "type": "new_property",
            "data": {...},
            "timestamp": "2026-02-21T10:30:00Z"
        }
    """
    # Получаем пользователя (опционально)
    user = None
    user_id = 0  # Анонимный пользователь

    if token:
        try:
            user = await get_current_user_optional(token)
            if user:
                user_id = user.id
        except Exception as e:
            logger.warning(f"WebSocket auth error: {e}")

    # Парсим каналы
    channel_list = [c.strip() for c in channels.split(",") if c.strip()]
    if not channel_list:
        channel_list = ["general"]  # Канал по умолчанию

    # Подключаем
    await manager.connect(websocket, user_id, channel_list)

    try:
        # Слушаем сообщения от клиента
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                await handle_client_message(websocket, user_id, message)
            except json.JSONDecodeError:
                await manager.send_personal_message(
                    websocket,
                    {"type": "error", "message": "Invalid JSON"}
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, channel_list)
        logger.info(f"WebSocket disconnected: user_id={user_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, user_id, channel_list)


async def handle_client_message(
    websocket: WebSocket,
    user_id: int,
    message: Dict[str, Any]
) -> None:
    """
    Обработать сообщение от клиента.

    Поддерживаемые команды:
        - subscribe: Подписаться на канал
        - unsubscribe: Отписаться от канала
        - ping: Проверка соединения
        - get_stats: Получить статистику
    """
    msg_type = message.get("type")

    if msg_type == "subscribe":
        channel = message.get("channel")
        if channel:
            if channel not in manager.channel_subscriptions:
                manager.channel_subscriptions[channel] = set()
            manager.channel_subscriptions[channel].add(user_id)

            await manager.send_personal_message(
                websocket,
                {"type": "subscribed", "channel": channel}
            )
            logger.info(f"User {user_id} subscribed to {channel}")

    elif msg_type == "unsubscribe":
        channel = message.get("channel")
        if channel and channel in manager.channel_subscriptions:
            manager.channel_subscriptions[channel].discard(user_id)

            await manager.send_personal_message(
                websocket,
                {"type": "unsubscribed", "channel": channel}
            )

    elif msg_type == "ping":
        await manager.send_personal_message(
            websocket,
            {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
        )

    elif msg_type == "get_stats":
        stats = manager.get_stats()
        await manager.send_personal_message(websocket, stats)


# ============================================================================
# Утилиты для отправки уведомлений
# ============================================================================

async def notify_new_property(
    property_data: Dict[str, Any],
    city: Optional[str] = None
) -> None:
    """
    Отправить уведомление о новом объявлении.

    Args:
        property_data: Данные объявления
        city: Город для фильтрации
    """
    message = {
        "type": "new_property",
        "data": property_data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Отправляем в канал новых объявлений
    await manager.broadcast_to_channel("new_properties", message)

    # Если есть город - отправляем в городской канал
    if city:
        city_channel = f"city:{city}"
        await manager.broadcast_to_channel(city_channel, message)


async def notify_price_drop(
    property_id: int,
    old_price: float,
    new_price: float,
    property_data: Dict[str, Any]
) -> None:
    """
    Отправить уведомление о снижении цены.

    Args:
        property_id: ID объявления
        old_price: Старая цена
        new_price: Новая цена
        property_data: Данные объявления
    """
    message = {
        "type": "price_drop",
        "data": {
            "property_id": property_id,
            "old_price": old_price,
            "new_price": new_price,
            "drop_percent": ((old_price - new_price) / old_price) * 100,
            "property": property_data,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

    await manager.broadcast_to_channel("price_drops", message)


async def notify_alert(
    user_id: int,
    alert_type: str,
    message_data: Dict[str, Any]
) -> None:
    """
    Отправить персональное оповещение.

    Args:
        user_id: ID пользователя
        alert_type: Тип оповещения
        message_data: Данные сообщения
    """
    message = {
        "type": "alert",
        "alert_type": alert_type,
        "data": message_data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    await manager.broadcast_to_user(user_id, message)


async def notify_system(
    message: str,
    level: str = "info"
) -> None:
    """
    Отправить системное уведомление всем.

    Args:
        message: Текст сообщения
        level: Уровень (info, warning, error)
    """
    await manager.broadcast_all({
        "type": "system",
        "level": level,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    })


# ============================================================================
# Страница для тестирования WebSocket
# ============================================================================

@router.get("/ws/test", response_class=HTMLResponse)
async def websocket_test_page():
    """Страница для тестирования WebSocket подключений."""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>RentScout WebSocket Test</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            #log { border: 1px solid #ccc; padding: 10px; height: 400px; overflow-y: auto; }
            .message { margin: 5px 0; padding: 5px; border-radius: 3px; }
            .sent { background: #e3fcef; }
            .received { background: #fff3cd; }
            .error { background: #f8d7da; }
            button { margin: 5px; padding: 8px 16px; }
            input { padding: 8px; margin: 5px; }
        </style>
    </head>
    <body>
        <h1>🔌 RentScout WebSocket Test</h1>

        <div>
            <input type="text" id="channels" placeholder="Channels (comma-separated)" value="new_properties,price_drops">
            <button onclick="connect()">Connect</button>
            <button onclick="disconnect()">Disconnect</button>
            <button onclick="sendPing()">Ping</button>
            <button onclick="getStats()">Get Stats</button>
        </div>

        <div style="margin-top: 10px;">
            <input type="text" id="subscribeChannel" placeholder="Channel to subscribe">
            <button onclick="subscribe()">Subscribe</button>
            <button onclick="unsubscribe()">Unsubscribe</button>
        </div>

        <h3>Log:</h3>
        <div id="log"></div>

        <script>
            let ws = null;
            const log = document.getElementById('log');

            function addLog(message, type = 'received') {
                const div = document.createElement('div');
                div.className = 'message ' + type;
                div.textContent = new Date().toLocaleTimeString() + ' - ' + JSON.stringify(message);
                log.appendChild(div);
                log.scrollTop = log.scrollHeight;
            }

            function connect() {
                const channels = document.getElementById('channels').value;
                const url = `ws://localhost:8000/ws/notifications?channels=${channels}`;

                ws = new WebSocket(url);

                ws.onopen = () => {
                    addLog({type: 'connected'}, 'sent');
                };

                ws.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    addLog(data, 'received');
                };

                ws.onclose = () => {
                    addLog({type: 'disconnected'}, 'error');
                    ws = null;
                };

                ws.onerror = (error) => {
                    addLog({type: 'error', error: error}, 'error');
                };
            }

            function disconnect() {
                if (ws) {
                    ws.close();
                    ws = null;
                }
            }

            function send(message) {
                if (ws) {
                    ws.send(JSON.stringify(message));
                    addLog(message, 'sent');
                }
            }

            function sendPing() {
                send({type: 'ping'});
            }

            function getStats() {
                send({type: 'get_stats'});
            }

            function subscribe() {
                const channel = document.getElementById('subscribeChannel').value;
                if (channel) {
                    send({type: 'subscribe', channel: channel});
                }
            }

            function unsubscribe() {
                const channel = document.getElementById('subscribeChannel').value;
                if (channel) {
                    send({type: 'unsubscribe', channel: channel});
                }
            }
        </script>
    </body>
    </html>
    """)


# ============================================================================
# Экспорт
# ============================================================================

__all__ = [
    "manager",
    "notify_new_property",
    "notify_price_drop",
    "notify_alert",
    "notify_system",
]
