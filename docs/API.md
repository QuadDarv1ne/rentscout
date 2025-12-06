# 📡 API Документация RentScout

## Оглавление
1. [Общая информация](#общая-информация)
2. [Аутентификация](#аутентификация)
3. [Endpoints](#endpoints)
4. [Коды ответов](#коды-ответов)
5. [Примеры запросов](#примеры-запросов)
6. [Лимиты и квоты](#лимиты-и-квоты)

---

## Общая информация

### URL базы
```
Production: https://api.rentscout.com
Development: http://localhost:8000
```

### Версия API
`1.0.0`

### Формат
- **Request Content-Type**: `application/json`
- **Response Content-Type**: `application/json`
- **Кодировка**: UTF-8

### Headers

Все запросы должны содержать стандартные HTTP headers:

```http
GET /api/properties HTTP/1.1
Host: api.rentscout.com
Content-Type: application/json
User-Agent: Mozilla/5.0
```

---

## Аутентификация

На данный момент API открыт для всех (публичный). 

Планируется добавить:
- API Key аутентификация
- OAuth 2.0
- JWT tokens

```http
GET /api/properties?city=Москва
Authorization: Bearer YOUR_API_KEY
```

---

## Endpoints

### 1. Health Check

Проверить статус API.

#### Request
```http
GET /api/health
```

#### Response

**Status Code:** `200 OK`

```json
{
  "status": "healthy",
  "timestamp": "2025-12-06T12:00:00Z",
  "version": "1.0.0"
}
```

---

### 2. Поиск недвижимости

Получить список объектов недвижимости с поддержкой фильтрации.

#### Request
```http
GET /api/properties?city=Москва&min_price=3000&max_price=5000&min_rooms=1&max_rooms=3
```

#### Query Parameters

| Параметр | Тип | Требуется | Описание | Пример |
|----------|-----|----------|---------|--------|
| `city` | string | ✅ Да | Название города | `Москва` |
| `property_type` | string | ❌ Нет | Тип недвижимости | `Квартира` |
| `min_price` | number | ❌ Нет | Минимальная цена (≥0) | `3000` |
| `max_price` | number | ❌ Нет | Максимальная цена (≥0) | `50000` |
| `min_rooms` | integer | ❌ Нет | Минимум комнат (≥0) | `1` |
| `max_rooms` | integer | ❌ Нет | Максимум комнат (≥0) | `3` |
| `min_area` | number | ❌ Нет | Минимальная площадь м² (≥0) | `30` |
| `max_area` | number | ❌ Нет | Максимальная площадь м² (≥0) | `80` |
| `district` | string | ❌ Нет | Район города | `Центральный` |
| `has_photos` | boolean | ❌ Нет | Наличие фотографий | `true` |
| `source` | string | ❌ Нет | Источник (avito, cian, etc) | `avito` |
| `max_price_per_sqm` | number | ❌ Нет | Макс цена за м² (≥0) | `1500` |

#### Response

**Status Code:** `200 OK`

```json
[
  {
    "id": "avito_123456789",
    "source": "avito",
    "external_id": "123456789",
    "title": "Квартира 1 комн. 45м² в центре",
    "price": 45000,
    "rooms": 1,
    "area": 45.0,
    "location": {
      "city": "Москва",
      "district": "Центральный",
      "address": "ул. Тверская, д. 5"
    },
    "photos": [
      "https://example.com/photo1.jpg",
      "https://example.com/photo2.jpg"
    ],
    "description": "Уютная квартира в центре города",
    "url": "https://avito.ru/moscow/квартиры/..."
  },
  {
    "id": "cian_987654321",
    "source": "cian",
    "external_id": "987654321",
    "title": "Квартира 2 комн. 65м² рядом с метро",
    "price": 55000,
    "rooms": 2,
    "area": 65.0,
    "location": {
      "city": "Москва",
      "district": "Красносельский",
      "address": "ул. Красносельская, д. 10"
    },
    "photos": [
      "https://example.com/photo3.jpg"
    ],
    "description": "Красивая квартира с ремонтом",
    "url": "https://cian.ru/rent/..."
  }
]
```

#### Response Schema

```typescript
interface Property {
  id: string;                          // Уникальный ID
  source: string;                      // Источник (avito, cian, ostrovok, etc)
  external_id: string;                 // ID в источнике
  title: string;                       // Название объявления
  price: number;                       // Цена в рублях
  rooms?: number;                      // Количество комнат
  area?: number;                       // Площадь в м²
  location?: {
    city?: string;
    district?: string;
    address?: string;
    latitude?: number;
    longitude?: number;
    [key: string]: any;
  };
  photos?: string[];                   // URLs фотографий
  description?: string;                // Описание
  url?: string;                        // URL на исходный сайт
  [key: string]: any;
}
```

---

## Коды ответов

| Код | Статус | Описание |
|-----|--------|---------|
| `200` | OK | Успешный запрос |
| `400` | Bad Request | Неправильные параметры запроса |
| `404` | Not Found | Ресурс не найден |
| `429` | Too Many Requests | Превышен лимит запросов |
| `500` | Internal Server Error | Ошибка сервера |
| `503` | Service Unavailable | Сервис временно недоступен |

### Примеры ошибок

#### 400 Bad Request
```json
{
  "detail": [
    {
      "loc": ["query", "city"],
      "msg": "ensure this value has at least 2 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

#### 429 Too Many Requests
```json
{
  "detail": "Rate limit exceeded. Maximum 100 requests per minute."
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Internal Server Error. Search service temporarily unavailable."
}
```

---

## Примеры запросов

### cURL

#### Базовый поиск
```bash
curl -X GET "http://localhost:8000/api/properties?city=Москва" \
  -H "Content-Type: application/json"
```

#### Поиск с фильтрацией
```bash
curl -X GET "http://localhost:8000/api/properties" \
  -H "Content-Type: application/json" \
  -G \
  -d "city=Москва" \
  -d "min_price=3000" \
  -d "max_price=50000" \
  -d "min_rooms=1" \
  -d "max_rooms=3" \
  -d "min_area=30" \
  -d "max_area=80"
```

#### Поиск с районом и фотографиями
```bash
curl -X GET "http://localhost:8000/api/properties" \
  -H "Content-Type: application/json" \
  -G \
  -d "city=Москва" \
  -d "district=Центральный" \
  -d "has_photos=true" \
  -d "source=avito"
```

### Python

```python
import requests
from typing import List, Dict

BASE_URL = "http://localhost:8000/api"

def search_properties(
    city: str,
    min_price: int = None,
    max_price: int = None,
    min_rooms: int = None,
    max_rooms: int = None,
    **filters
) -> List[Dict]:
    """Поиск недвижимости через API."""
    
    params = {
        "city": city,
        "min_price": min_price,
        "max_price": max_price,
        "min_rooms": min_rooms,
        "max_rooms": max_rooms,
        **filters
    }
    
    # Удаляем None значения
    params = {k: v for k, v in params.items() if v is not None}
    
    response = requests.get(
        f"{BASE_URL}/properties",
        params=params,
        timeout=30
    )
    
    response.raise_for_status()
    return response.json()

# Использование
properties = search_properties(
    city="Москва",
    min_price=3000,
    max_price=50000,
    min_rooms=1,
    max_rooms=3,
    district="Центральный"
)

for prop in properties:
    print(f"{prop['title']} - {prop['price']} руб.")
```

### JavaScript

```javascript
// Fetch
const searchProperties = async (filters) => {
  const params = new URLSearchParams(filters);
  
  try {
    const response = await fetch(
      `http://localhost:8000/api/properties?${params}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Search error:', error);
    throw error;
  }
};

// Использование
searchProperties({
  city: 'Москва',
  min_price: 3000,
  max_price: 50000,
  min_rooms: 1,
  max_rooms: 3
}).then(properties => {
  console.log('Found properties:', properties);
}).catch(error => {
  console.error('Error:', error);
});
```

### Axios (JavaScript)

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 30000
});

const searchProperties = async (filters) => {
  try {
    const response = await api.get('/properties', { params: filters });
    return response.data;
  } catch (error) {
    console.error('Search error:', error.response?.data || error.message);
    throw error;
  }
};

// Использование
const properties = await searchProperties({
  city: 'Москва',
  min_price: 3000,
  max_price: 50000
});
```

---

## Лимиты и квоты

### Rate Limiting

API использует алгоритм `Token Bucket` для ограничения частоты запросов.

| Тип клиента | Лимит | Окно | Reset |
|-------------|-------|------|-------|
| Anonymous | 100 | 60 сек | Каждую минуту |
| API Key | 1000 | 60 сек | Каждую минуту |
| Premium | Unlimited | - | - |

### Размеры данных

| Параметр | Лимит |
|----------|-------|
| Макс результатов на запрос | 1000 |
| Макс размер ответа | 10 MB |
| Макс длина query параметра | 1024 символа |

### Headers ответа

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1638777660
X-Response-Time: 245ms
```

---

## Кеширование

API использует кеширование с TTL (Time To Live).

| Endpoint | TTL | Условия инвалидации |
|----------|-----|-------------------|
| `/api/properties` | 5 минут | Новые объявления |
| `/api/health` | 30 сек | Статус сервиса |

### Cache Headers

```http
Cache-Control: public, max-age=300
ETag: "abc123def456"
Last-Modified: Sat, 04 Dec 2021 07:00:00 GMT
```

---

## Обработка ошибок

### Стратегия retry

Клиенты должны реализовать экспоненциальный backoff при получении ошибок 5xx:

```python
import time
import requests

def request_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1, 2, 4 секунды
                print(f"Request failed, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise
```

---

## Асинхронное использование

### WebSocket (планируется)

Для получения обновлений в реальном времени:

```javascript
const ws = new WebSocket('wss://api.rentscout.com/ws/properties');

ws.onmessage = (event) => {
  const property = JSON.parse(event.data);
  console.log('New property:', property);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

---

## Версионирование

Текущая версия: `1.0.0`

Поддерживаемые версии:
- `v1` - текущая (все запросы идут в `/api/properties`)

Планируется:
- `v2` - с улучшенной фильтрацией и sorting

---

## Тестирование API

### Swagger UI
```
http://localhost:8000/docs
```

### ReDoc
```
http://localhost:8000/redoc
```

### Postman

Импортируйте OpenAPI спеку:
```
http://localhost:8000/openapi.json
```

---

## Поддержка

- **Issues**: https://github.com/QuadDarv1ne/rentscout/issues
- **Email**: support@rentscout.com
- **Documentation**: https://docs.rentscout.com

---

**Последнее обновление:** Декабрь 2025
**Версия API:** 1.0.0
