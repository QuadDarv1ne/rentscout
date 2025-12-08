# 🔔 RentScout Notifications & Bookmarks - v1.5.0

Полное руководство по использованию новых компонентов уведомлений и закладок.

---

## 📌 Быстрый старт

### 1. WebSocket Уведомления

```python
import asyncio
import websockets
import json

async def listen_notifications():
    uri = "ws://localhost:8000/api/notifications/ws?topic=city:moskva"
    async with websockets.connect(uri) as websocket:
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Event: {data['event_type']}")
            print(f"Data: {data['data']}")

asyncio.run(listen_notifications())
```

### 2. Добавить в Избранное

```bash
curl -X POST "http://localhost:8000/api/bookmarks/add?user_id=user123" \
  -H "Content-Type: application/json" \
  -d '{
    "external_property_id": "avito_12345",
    "property_title": "2-комнатная квартира",
    "property_source": "avito",
    "property_price": 50000,
    "property_city": "Москва",
    "property_link": "https://avito.ru/moskva/kvartiry/..."
  }'
```

### 3. Получить Рекомендации

```bash
curl "http://localhost:8000/api/bookmarks/recommendations?user_id=user123&limit=10"
```

---

## 🔔 API Уведомлений

### WebSocket Подключение

**URL:** `ws://localhost:8000/api/notifications/ws`

**Параметры:**
- `topic` - Топик подписки (default: `general`)

**Топики:**
- `general` - Все события
- `city:moskva` - События Москвы
- `city:spb` - События СПб
- `price_changes` - Изменение цен
- `alerts` - Срабатывания алертов

**Пример:**
```bash
# Используя wscat
wscat -c "ws://localhost:8000/api/notifications/ws?topic=city:moskva"

# Используя Python
import websocket

ws = websocket.WebSocket()
ws.connect("ws://localhost:8000/api/notifications/ws?topic=general")

# Отправить ping для keep-alive
ws.send("ping")

# Получить сообщение
msg = ws.recv()  # {"event_type": "new_property", ...}
```

### REST API

#### Отправить Email Уведомление

```http
POST /api/notifications/email/send
Content-Type: application/json

{
  "to_email": "user@example.com",
  "subject": "Найдены новые объявления",
  "body": "5 новых объявлений по вашим критериям",
  "html_body": "<h1>5 новых объявлений</h1><p>...</p>"
}
```

**Response:**
```json
{
  "status": "sent",
  "to": "user@example.com",
  "subject": "Найдены новые объявления"
}
```

#### Тестовое Email

```http
POST /api/notifications/email/test?email=user@example.com
```

#### Статистика WebSocket

```http
GET /api/notifications/ws/stats
GET /api/notifications/ws/stats?topic=city:moskva
```

**Response:**
```json
{
  "total_connections": 42,
  "topics": {
    "general": 10,
    "city:moskva": 20,
    "city:spb": 12
  }
}
```

#### Health Check

```http
GET /api/notifications/health
```

**Response:**
```json
{
  "status": "healthy",
  "websocket": {
    "enabled": true,
    "connections": 42,
    "topics": ["general", "city:moskva", "alerts"]
  },
  "email": {
    "enabled": true,
    "smtp_host": "smtp.gmail.com"
  }
}
```

---

## ⭐ API Закладок

### Добавить в Избранное/Закладки

```http
POST /api/bookmarks/add?user_id=user123
Content-Type: application/json

{
  "external_property_id": "avito_12345",
  "property_title": "2-комнатная квартира",
  "property_source": "avito",
  "property_price": 50000,
  "property_city": "Москва",
  "property_link": "https://...",
  "bookmark_type": "favorite",
  "notes": "Хороший вариант",
  "rating": 4,
  "tags": ["центр", "квартира"]
}
```

**Типы закладок:**
- `favorite` - Избранное
- `bookmark` - Коллекция (требует `collection_name`)
- `viewed` - Просмотренные
- `compare` - Для сравнения

### Получить Избранное

```http
GET /api/bookmarks/favorites?user_id=user123&city=Москва&skip=0&limit=50
```

**Response:**
```json
{
  "count": 15,
  "items": [...],
  "skip": 0,
  "limit": 50
}
```

### Получить Закладки Коллекции

```http
GET /api/bookmarks/bookmarks?user_id=user123&collection=Мои избранные
```

### Получить Все Коллекции

```http
GET /api/bookmarks/collections?user_id=user123
```

**Response:**
```json
{
  "count": 3,
  "collections": ["Мои избранные", "Для анализа", "Недорогие"]
}
```

### История Просмотров

```http
GET /api/bookmarks/history?user_id=user123&days=30&limit=100
```

**Response:**
```json
{
  "count": 45,
  "period_days": 30,
  "items": [...]
}
```

### Статистика

```http
GET /api/bookmarks/stats?user_id=user123
```

**Response:**
```json
{
  "total_favorites": 15,
  "total_bookmarks": 8,
  "total_viewed": 120,
  "collections_count": 3,
  "tags_count": 42,
  "favorite_cities": {
    "Москва": 12,
    "Санкт-Петербург": 3
  },
  "favorite_sources": {
    "avito": 10,
    "cian": 5
  },
  "favorite_price_range": {
    "min": 30000,
    "max": 100000,
    "avg": 55000
  }
}
```

### Рекомендации

```http
GET /api/bookmarks/recommendations?user_id=user123&limit=10
```

**Response:**
```json
[
  {
    "external_id": "avito_54321",
    "title": "Квартира на Невском",
    "price": 45000,
    "city": "Санкт-Петербург",
    "reason": "Соответствует вашим предпочтениям по городу и цене",
    "similarity_score": 0.85
  }
]
```

### Обновить Закладку

```http
PUT /api/bookmarks/update/avito_12345?user_id=user123
Content-Type: application/json

{
  "notes": "Обновленная заметка",
  "rating": 5,
  "tags": ["отличный вариант", "центр"],
  "collection_name": "Новая коллекция"
}
```

### Удалить Закладку

```http
DELETE /api/bookmarks/remove?user_id=user123&external_property_id=avito_12345
```

### Добавить для Сравнения

```http
POST /api/bookmarks/compare?user_id=user123&external_property_id=avito_12345
```

### Получить Список Сравнения

```http
GET /api/bookmarks/compare?user_id=user123
```

### Очистить Список Сравнения

```http
POST /api/bookmarks/compare/clear?user_id=user123
```

---

## 🔧 Конфигурация

### Email (SMTP)

Добавьте в `.env` или `app/core/config.py`:

```python
SMTP_HOST = "smtp.gmail.com"  # или другой SMTP сервер
SMTP_PORT = 587
SMTP_USERNAME = "your-email@gmail.com"
SMTP_PASSWORD = "your-app-specific-password"
SMTP_FROM_EMAIL = "noreply@rentscout.com"
```

### Для Gmail:
1. Включить 2FA на аккаунте
2. Создать App Password на https://myaccount.google.com/apppasswords
3. Использовать этот пароль в `SMTP_PASSWORD`

---

## 📚 Примеры Кода

### Python Клиент

```python
import requests
import json

# Конфигурация
BASE_URL = "http://localhost:8000/api"
USER_ID = "user123"

class RentScoutClient:
    def __init__(self, base_url, user_id):
        self.base_url = base_url
        self.user_id = user_id
    
    def add_favorite(self, property_data):
        """Добавить в избранное"""
        response = requests.post(
            f"{self.base_url}/bookmarks/add?user_id={self.user_id}",
            json={
                "bookmark_type": "favorite",
                **property_data
            }
        )
        return response.json()
    
    def get_favorites(self, city=None):
        """Получить избранное"""
        params = {"user_id": self.user_id}
        if city:
            params["city"] = city
        
        response = requests.get(
            f"{self.base_url}/bookmarks/favorites",
            params=params
        )
        return response.json()
    
    def get_recommendations(self, limit=10):
        """Получить рекомендации"""
        response = requests.get(
            f"{self.base_url}/bookmarks/recommendations",
            params={
                "user_id": self.user_id,
                "limit": limit
            }
        )
        return response.json()
    
    def get_stats(self):
        """Получить статистику"""
        response = requests.get(
            f"{self.base_url}/bookmarks/stats",
            params={"user_id": self.user_id}
        )
        return response.json()

# Использование
client = RentScoutClient(BASE_URL, USER_ID)

# Добавить в избранное
fav = client.add_favorite({
    "external_property_id": "avito_123",
    "property_title": "Квартира",
    "property_source": "avito",
    "property_price": 50000,
    "property_city": "Москва",
    "property_link": "https://..."
})

# Получить рекомендации
recommendations = client.get_recommendations(limit=10)
for rec in recommendations:
    print(f"{rec['title']} - {rec['price']} ₽ ({rec['reason']})")

# Статистика
stats = client.get_stats()
print(f"Всего избранных: {stats['total_favorites']}")
print(f"Популярные города: {stats['favorite_cities']}")
```

### JavaScript/Node.js Клиент

```javascript
const BASE_URL = 'http://localhost:8000/api';
const USER_ID = 'user123';

class RentScoutClient {
  async addFavorite(propertyData) {
    const response = await fetch(
      `${BASE_URL}/bookmarks/add?user_id=${USER_ID}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bookmark_type: 'favorite',
          ...propertyData
        })
      }
    );
    return response.json();
  }
  
  async getFavorites(city = null) {
    const params = new URLSearchParams({ user_id: USER_ID });
    if (city) params.append('city', city);
    
    const response = await fetch(
      `${BASE_URL}/bookmarks/favorites?${params}`
    );
    return response.json();
  }
  
  async getRecommendations(limit = 10) {
    const params = new URLSearchParams({
      user_id: USER_ID,
      limit: limit
    });
    
    const response = await fetch(
      `${BASE_URL}/bookmarks/recommendations?${params}`
    );
    return response.json();
  }
  
  connectWebSocket(topic = 'general') {
    const ws = new WebSocket(
      `ws://localhost:8000/api/notifications/ws?topic=${topic}`
    );
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Event:', data.event_type, data.data);
    };
    
    return ws;
  }
}

// Использование
const client = new RentScoutClient();

// WebSocket слушатель
const ws = client.connectWebSocket('city:moskva');

// Добавить в избранное
await client.addFavorite({
  external_property_id: 'avito_123',
  property_title: 'Квартира',
  property_source: 'avito',
  property_price: 50000,
  property_city: 'Москва',
  property_link: 'https://...'
});

// Рекомендации
const recommendations = await client.getRecommendations(10);
recommendations.forEach(rec => {
  console.log(`${rec.title} - ${rec.price} ₽`);
});
```

---

## 🧪 Тестирование

### Запустить все тесты уведомлений

```bash
pytest app/tests/test_notifications.py -v
pytest app/tests/test_notifications_api.py -v
```

### Запустить все тесты закладок

```bash
pytest app/tests/test_bookmarks.py -v
```

### Запустить конкретный тест

```bash
pytest app/tests/test_notifications.py::test_websocket_connect -v
pytest app/tests/test_bookmarks.py::test_full_bookmark_workflow -v
```

---

## 📊 Производительность

- **WebSocket:** <1ms задержка для broadcast
- **Email:** Асинхронная отправка, не блокирует API
- **Закладки:** O(1) lookup по user_id благодаря индексам

---

## 🐛 Troubleshooting

### Email не отправляется

1. Проверить SMTP конфигурацию
   ```bash
   curl "http://localhost:8000/api/notifications/health" | grep email
   ```

2. Протестировать email
   ```bash
   curl -X POST "http://localhost:8000/api/notifications/email/test?email=test@example.com"
   ```

3. Проверить логи
   ```bash
   tail -f app.log | grep "email"
   ```

### WebSocket не подключается

1. Проверить адрес
   ```bash
   wscat -c "ws://localhost:8000/api/notifications/ws?topic=general"
   ```

2. Проверить stats
   ```bash
   curl "http://localhost:8000/api/notifications/ws/stats"
   ```

### Закладки не сохраняются

1. Проверить БД
   ```bash
   docker-compose exec db psql -U postgres -d rentscout -c "SELECT COUNT(*) FROM user_bookmarks;"
   ```

2. Проверить health
   ```bash
   curl "http://localhost:8000/api/bookmarks/health"
   ```

---

## 📝 Лицензия

MIT - See LICENSE file for details

**RentScout v1.5.0** ✨
