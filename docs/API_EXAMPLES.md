# 📚 RentScout API Examples

Примеры запросов ко всем основным endpoint'ам API.

---

## 🔑 Оглавление

1. [Аутентификация](#authentication)
2. [Поиск объявлений](#properties)
3. [ML Предсказания](#ml-predictions)
4. [Закладки и Избранное](#bookmarks)
5. [Уведомления](#notifications)
6. [Health и Метрики](#health--metrics)

---

## Authentication {#authentication}

### Регистрация пользователя

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "email": "john@example.com",
    "password": "StrongPass123!"
  }'
```

**Ответ:**
```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "role": "user",
  "created_at": "2026-02-21T10:00:00",
  "updated_at": "2026-02-21T10:00:00",
  "is_active": true,
  "is_verified": false
}
```

---

### Вход в систему (Login)

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=john_doe&password=StrongPass123!"
```

**Ответ:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

---

### Обновление токенов (Refresh)

```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'
```

---

### Получение профиля

```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

### Обновление профиля

```bash
curl -X PUT http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "new_username",
    "email": "new@example.com"
  }'
```

---

### Выход из системы

```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Properties {#properties}

### Поиск объявлений

```bash
curl -X GET "http://localhost:8000/api/properties?city=Москва&min_price=30000&max_price=60000&min_rooms=1&max_rooms=2"
```

**Параметры:**
- `city` — город (обязательно)
- `min_price` — минимальная цена
- `max_price` — максимальная цена
- `min_rooms` — минимальное количество комнат
- `max_rooms` — максимальное количество комнат
- `min_area` — минимальная площадь
- `max_area` — максимальная площадь
- `source` — источник (avito, cian, и т.д.)

**Ответ:**
```json
{
  "city": "Москва",
  "total_results": 150,
  "cached": false,
  "properties": [
    {
      "id": "avito_12345",
      "title": "2-к квартира, 54 м²",
      "price": 50000,
      "rooms": 2,
      "area": 54,
      "source": "avito",
      "url": "https://avito.ru/...",
      "image": "https://...",
      "created_at": "2026-02-21T10:00:00"
    }
  ]
}
```

---

### Расширенный поиск

```bash
curl -X POST http://localhost:8000/api/advanced-search \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Москва",
    "filters": {
      "min_price": 40000,
      "max_price": 80000,
      "rooms": [1, 2],
      "min_area": 40,
      "districts": ["ЦАО", "ЗАО"]
    },
    "sort_by": "price_asc"
  }'
```

---

### Объявления из БД

```bash
curl -X GET "http://localhost:8000/api/db/properties?city=Москва&limit=20&offset=0"
```

---

## ML Predictions {#ml-predictions}

### Предсказание цены

```bash
curl -X POST http://localhost:8000/api/ml/predict-price \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Москва",
    "rooms": 2,
    "area": 54.5,
    "district": "ЦАО",
    "floor": 5,
    "total_floors": 12,
    "is_verified": true
  }'
```

**Ответ:**
```json
{
  "predicted_price": 52000,
  "confidence": 0.85,
  "price_range": [48000, 56000],
  "factors": {
    "city_factor": 1.2,
    "rooms_factor": 1.0,
    "area_factor": 0.95,
    "district_factor": 1.15
  },
  "trend": "stable",
  "recommendation": "Цена соответствует рынку"
}
```

---

### Сравнение цены

```bash
curl -X POST http://localhost:8000/api/ml/compare-price \
  -H "Content-Type: application/json" \
  -d '{
    "actual_price": 55000,
    "city": "Москва",
    "rooms": 2,
    "area": 54.0
  }'
```

**Ответ:**
```json
{
  "actual_price": 55000,
  "predicted_price": 52000,
  "difference": 3000,
  "percentage_difference": 5.77,
  "rating": "slightly_high",
  "comment": "Цена на 5.77% выше рыночной"
}
```

---

### Статистика цен по городу

```bash
curl -X GET "http://localhost:8000/api/ml/price-statistics/Москва?rooms=2&days=30"
```

---

### Тренд рынка

```bash
curl -X GET "http://localhost:8000/api/ml/market-trend/Москва?rooms=2"
```

**Ответ:**
```json
{
  "city": "Москва",
  "rooms": 2,
  "trend": "up",
  "comment": "Цены растут на 3% в месяц",
  "stats_7_days": {
    "average_price": 53000,
    "count": 150
  },
  "stats_30_days": {
    "average_price": 51000,
    "count": 600
  },
  "change_percentage": 3.92
}
```

---

### Оптимальная цена

```bash
curl -X POST http://localhost:8000/api/ml/optimal-price \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Москва",
    "rooms": 2,
    "area": 54.0,
    "district": "ЗАО"
  }'
```

**Ответ:**
```json
{
  "optimal_price": 52500,
  "min_competitive": 49000,
  "max_competitive": 56000,
  "market_average": 53000,
  "confidence": 0.82
}
```

---

## Bookmarks {#bookmarks}

### Добавить в избранное

```bash
curl -X POST "http://localhost:8000/api/bookmarks/add?user_id=user-123" \
  -H "Content-Type: application/json" \
  -d '{
    "external_property_id": "avito_12345",
    "property_title": "2-к квартира, 54 м²",
    "property_source": "avito",
    "property_price": 50000,
    "property_city": "Москва",
    "property_link": "https://avito.ru/...",
    "bookmark_type": "favorite",
    "tags": ["хороший вариант", "центр"],
    "rating": 5
  }'
```

---

### Добавить в коллекцию

```bash
curl -X POST "http://localhost:8000/api/bookmarks/add?user_id=user-123" \
  -H "Content-Type: application/json" \
  -d '{
    "external_property_id": "cian_67890",
    "property_title": "1-к квартира, 40 м²",
    "property_source": "cian",
    "property_price": 40000,
    "property_city": "Санкт-Петербург",
    "property_link": "https://cian.ru/...",
    "bookmark_type": "bookmark",
    "collection_name": "Подходящие варианты",
    "notes": "Позвонить в выходные"
  }'
```

---

### Получить избранное

```bash
curl -X GET "http://localhost:8000/api/bookmarks/favorites?user_id=user-123"
```

---

### Получить закладки по коллекции

```bash
curl -X GET "http://localhost:8000/api/bookmarks/collection/Подходящие%20варианты?user_id=user-123"
```

---

### Обновить закладку

```bash
curl -X PUT "http://localhost:8000/api/bookmarks/1?user_id=user-123" \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Обновлённая заметка",
    "tags": ["новый тег"],
    "rating": 4
  }'
```

---

### Удалить закладку

```bash
curl -X DELETE "http://localhost:8000/api/bookmarks/1?user_id=user-123"
```

---

### Статистика закладок

```bash
curl -X GET "http://localhost:8000/api/bookmarks/stats?user_id=user-123"
```

**Ответ:**
```json
{
  "total_favorites": 15,
  "total_bookmarks": 30,
  "total_viewed": 100,
  "collections_count": 3,
  "tags_count": 12,
  "favorite_cities": {
    "Москва": 20,
    "Санкт-Петербург": 10
  },
  "favorite_sources": {
    "avito": 25,
    "cian": 15
  }
}
```

---

### Рекомендации

```bash
curl -X GET "http://localhost:8000/api/bookmarks/recommendations?user_id=user-123&limit=10"
```

---

## Notifications {#notifications}

### Статистика WebSocket

```bash
curl -X GET "http://localhost:8000/api/notifications/ws/stats"
```

**Ответ:**
```json
{
  "total_connections": 25,
  "topics": {
    "general": 10,
    "city:москва": 8,
    "city:спб": 5,
    "price_changes": 2
  }
}
```

---

### Отправить email уведомление

```bash
curl -X POST http://localhost:8000/api/notifications/email/send \
  -H "Content-Type: application/json" \
  -d '{
    "to_email": "user@example.com",
    "subject": "Новое объявление по вашим критериям",
    "body": "Найдено новое объявление в Москве за 50000₽",
    "html_body": "<h1>Новое объявление!</h1><p>Найдено новое объявление в Москве за 50000₽</p>"
  }'
```

---

### Тестовое email

```bash
curl -X POST "http://localhost:8000/api/notifications/email/test?email=test@example.com"
```

---

## Health & Metrics {#health--metrics}

### Проверка здоровья (Health Check)

```bash
curl -X GET http://localhost:8000/api/health
```

**Ответ:**
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "redis": "connected",
    "celery": "running"
  },
  "version": "2.3.0",
  "uptime": 86400
}
```

---

### Детальная проверка здоровья

```bash
curl -X GET http://localhost:8000/api/health/detailed
```

---

### Метрики Prometheus

```bash
curl -X GET http://localhost:8000/metrics
```

**Ответ (текстовый формат Prometheus):**
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/properties"} 1500
http_requests_total{method="POST",path="/api/auth/login"} 300
...
```

---

### Статистика кеша

```bash
curl -X GET http://localhost:8000/api/cache/stats
```

---

### Статистика rate limiting

```bash
curl -X GET http://localhost:8000/api/rate-limit/stats
```

---

## 📝 Примеры на Python

### Использование с httpx (async)

```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Login
        response = await client.post("/api/auth/login", data={
            "username": "john_doe",
            "password": "StrongPass123!"
        })
        tokens = response.json()
        access_token = tokens["access_token"]

        # Поиск объявлений
        response = await client.get(
            "/api/properties",
            params={"city": "Москва", "max_price": 60000}
        )
        properties = response.json()

        # Предсказание цены
        response = await client.post(
            "/api/ml/predict-price",
            json={
                "city": "Москва",
                "rooms": 2,
                "area": 54.5
            }
        )
        prediction = response.json()

        # Добавить в избранное
        response = await client.post(
            "/api/bookmarks/add?user_id=user-123",
            json={
                "external_property_id": "avito_123",
                "property_title": "2-к квартира, 54 м²",
                "property_source": "avito",
                "property_price": 50000,
                "property_city": "Москва",
                "property_link": "https://avito.ru/...",
                "bookmark_type": "favorite"
            },
            headers={"Authorization": f"Bearer {access_token}"}
        )

asyncio.run(main())
```

---

### Использование с requests (sync)

```python
import requests

BASE_URL = "http://localhost:8000"

# Login
response = requests.post(
    f"{BASE_URL}/api/auth/login",
    data={"username": "john_doe", "password": "StrongPass123!"}
)
tokens = response.json()
access_token = tokens["access_token"]

# Поиск объявлений
response = requests.get(
    f"{BASE_URL}/api/properties",
    params={"city": "Москва", "max_price": 60000}
)
properties = response.json()

# Предсказание цены
response = requests.post(
    f"{BASE_URL}/api/ml/predict-price",
    json={"city": "Москва", "rooms": 2, "area": 54.5}
)
prediction = response.json()

print(f"Предсказанная цена: {prediction['predicted_price']}₽")
```

---

## 📊 Примеры на JavaScript (Fetch)

```javascript
const BASE_URL = 'http://localhost:8000';

// Login
async function login(username, password) {
  const response = await fetch(`${BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ username, password })
  });
  return response.json();
}

// Поиск объявлений
async function searchProperties(city, maxPrice) {
  const response = await fetch(
    `${BASE_URL}/api/properties?city=${city}&max_price=${maxPrice}`
  );
  return response.json();
}

// Предсказание цены
async function predictPrice(data) {
  const response = await fetch(`${BASE_URL}/api/ml/predict-price`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  return response.json();
}

// Использование
(async () => {
  const tokens = await login('john_doe', 'StrongPass123!');
  console.log('Access token:', tokens.access_token);

  const properties = await searchProperties('Москва', 60000);
  console.log('Найдено объявлений:', properties.total_results);

  const prediction = await predictPrice({
    city: 'Москва',
    rooms: 2,
    area: 54.5
  });
  console.log('Предсказанная цена:', prediction.predicted_price);
})();
```

---

## 🔗 Полезные ссылки

- [Swagger UI](http://localhost:8000/docs) — Интерактивная документация
- [ReDoc](http://localhost:8000/redoc) — Альтернативная документация
- [OpenAPI JSON](http://localhost:8000/openapi.json) — Спецификация API

---

**Последнее обновление:** 21 февраля 2026 г.
