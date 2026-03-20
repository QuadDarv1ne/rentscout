# 📊 Анализ API и рекомендации по улучшению

**Дата:** 20 марта 2026 г.
**Статус:** v2.5.0

---

## 1. Текущие API Endpoints

### 🔐 Authentication & Users
| Endpoint | Method | Описание | Статус |
|----------|--------|----------|--------|
| `/api/auth/register` | POST | Регистрация пользователя | ✅ Работает |
| `/api/auth/login` | POST | Вход в систему | ✅ Работает |
| `/api/auth/logout` | POST | Выход с отзывом токена | ✅ Работает |
| `/api/auth/refresh` | POST | Обновление токена | ✅ Работает |
| `/api/auth/2fa/enable` | POST | Включение 2FA | ✅ Работает |
| `/api/auth/2fa/verify` | POST | Проверка 2FA кода | ✅ Работает |
| `/api/auth/2fa/disable` | POST | Отключение 2FA | ✅ Работает |

### 🏠 Properties (Поиск)
| Endpoint | Method | Описание | Статус |
|----------|--------|----------|--------|
| `/api/properties` | GET | Поиск с фильтрами (15+ параметров) | ✅ Работает |
| `/api/advanced-search` | POST | Расширенный поиск | ✅ Работает |
| `/api/db/properties` | GET | CRUD операции с БД | ✅ Работает |
| `/api/db/properties/{id}` | GET/PUT/DELETE | Операции по ID | ✅ Работает |
| `/batch/*` | POST | Пакетные операции | ✅ Работает |

### 📊 Analytics & Metrics
| Endpoint | Method | Описание | Статус |
|----------|--------|----------|--------|
| `/metrics` | GET | Prometheus метрики | ✅ Работает |
| `/api/metrics/*` | GET | Расширенные метрики | ✅ Работает |
| `/api/analytics/*` | GET/POST | Аналитика рынка | ✅ Работает |
| `/api/quality-metrics` | GET | Метрики качества | ✅ Работает |

### 🔔 Notifications & Bookmarks
| Endpoint | Method | Описание | Статус |
|----------|--------|----------|--------|
| `/api/bookmarks/*` | GET/POST/DELETE | Закладки/избранное | ✅ Работает |
| `/api/notifications` | GET | Уведомления | ✅ Работает |
| `/api/ws` | WebSocket | Real-time уведомления | ✅ Работает |

### 🧠 ML & Predictions
| Endpoint | Method | Описание | Статус |
|----------|--------|----------|--------|
| `/api/ml/predict` | POST | Предсказание цены | ✅ Работает |
| `/api/ml/cache-ttl` | GET/POST | Управление ML кешем | ✅ Работает |

### 📦 Export & Import
| Endpoint | Method | Описание | Статус |
|----------|--------|----------|--------|
| `/api/export/properties` | GET | Экспорт в CSV/JSON/XLSX | ✅ Работает |
| `/api/export/progress` | GET | Прогресс экспорта | ✅ Работает |

### 🏥 Health & Monitoring
| Endpoint | Method | Описание | Статус |
|----------|--------|----------|--------|
| `/api/health` | GET | Базовый health check | ✅ Работает |
| `/api/health/detailed` | GET | Расширенная проверка | ✅ Работает |
| `/api/health/parsers` | GET | Статус парсеров | ✅ Работает |
| `/api/health/db` | GET | Статус БД | ✅ Работает |
| `/api/health/redis` | GET | Статус Redis | ✅ Работает |

### 🔧 System & Debugging
| Endpoint | Method | Описание | Статус |
|----------|--------|----------|--------|
| `/api/tasks/*` | GET/POST | Фоновые задачи | ✅ Работает |
| `/cache/*` | GET/POST | Управление кешем | ✅ Работает |
| `/system/*` | GET | Информация о системе | ✅ Работает |
| `/tracing/*` | GET | Distributed tracing | ✅ Работает |

---

## 2. Источники для парсинга

### ✅ Текущие парсеры

| Источник | Тип | Статус | Регион |
|----------|-----|--------|--------|
| **Avito** | Жильё | ✅ Работает | Россия |
| **Cian** | Жильё | ✅ Работает | Россия |
| **Domofond** | Жильё | ✅ Работает | Россия |
| **Domclick** | Жильё | ✅ Работает | Россия |
| **Yandex Realty** | Жильё | ✅ Работает | Россия |
| **Yandex Travel** | Отели | ✅ Работает | Россия |
| **Ostrovok** | Отели | ✅ Работает | Россия |
| **Otello** | Отели | ✅ Работает | Россия |
| **Sutochno** | Посуточно | ✅ Работает | Россия |
| **Tvil** | Посуточно | ✅ Работает | Россия |

### 🔴 Потенциальные источники для добавления

#### Жильё (Россия)
| Источник | Приоритет | Сложность | Комментарий |
|----------|-----------|-----------|-------------|
| **Etagi.com** | Высокий | Средняя | Крупный портал |
| **Mirkvartir.ru** | Высокий | Средняя | Много объявлений |
| **Ndom.ru** | Средний | Низкая | Простая структура |
| **Resale.ru** | Средний | Средняя | Вторичное жильё |
| **Avangard-realty.ru** | Низкий | Высокая | Агрегатор |

#### Коммерческая недвижимость
| Источник | Приоритет | Сложность | Комментарий |
|----------|-----------|-----------|-------------|
| **Cian Commercial** | Высокий | Средняя | Отдельный раздел |
| **Avito Commercial** | Высокий | Низкая | Есть категория |
| **Realto.ru** | Высокий | Средняя | Коммерческая платформа |
| **Office.ru** | Средний | Низкая | Офисы |
| **Retail.ru** | Низкий | Средняя | Ритейл помещения |

#### Зарубежная недвижимость
| Источник | Приоритет | Сложность | Комментарий |
|----------|-----------|-----------|-------------|
| **Rightmove (UK)** | Средний | Высокая | Блокировки |
| **Idealista (EU)** | Средний | Высокая | API ограничения |
| **Zillow (USA)** | Низкий | Высокая | Сложная защита |
| **Fang (China)** | Низкий | Очень высокая | Языковой барьер |

#### Агрегаторы
| Источник | Приоритет | Сложность | Комментарий |
|----------|-----------|-----------|-------------|
| **Google Hotels** | Высокий | Очень высокая | API платный |
| **Booking.com** | Высокий | Высокая | Партнёрская программа |
| **Airbnb** | Высокий | Очень высокая | Сильная защита |
| **TripAdvisor** | Средний | Высокая | Есть API |

#### Открытые данные
| Источник | Приоритет | Сложность | Комментарий |
|----------|-----------|-----------|-------------|
| **Росреестр** | Высокий | Средняя | Официальные данные |
| **Дом.Клик API** | Средний | Низкая | Публичное API |
| **OpenStreetMap** | Высокий | Низкая | Бесплатно |
| **2GIS API** | Средний | Низкая | Есть лимиты |

---

## 3. Рекомендации по новым API

### 🔥 Высокий приоритет

#### 3.1 Сравнение объектов
```python
POST /api/properties/compare
{
  "property_ids": [1, 2, 3],
  "metrics": ["price", "area", "location", "features"]
}

Response: {
  "comparison_table": {...},
  "recommendation": "best_value",
  "score": 0.85
}
```

#### 3.2 История цен
```python
GET /api/properties/{id}/price-history
GET /api/price-history/trends?city=Москва&property_type=Квартира

Response: {
  "history": [...],
  "trend": "increasing",
  "forecast": {...}
}
```

#### 3.3 Геолокация и карта
```python
GET /api/properties/nearby
  ?lat=55.7558
  &lon=37.6173
  &radius=1000

GET /api/properties/heatmap
  ?city=Москва
  &property_type=Квартира
```

#### 3.4 Уведомления о снижении цены
```python
POST /api/alerts/price-drop
{
  "property_id": 123,
  "threshold_percent": 10
}

GET /api/alerts
DELETE /api/alerts/{id}
```

#### 3.5 Отзывы о домах/ЖК
```python
POST /api/reviews/building
GET /api/reviews/building/{id}
POST /api/reviews/{id}/vote
```

### 🟡 Средний приоритет

#### 3.6 Избранное с папками
```python
POST /api/favorites/folder
PUT /api/favorites/{id}/move-to-folder
GET /api/favorites/folders
```

#### 3.7 Совместный просмотр
```python
POST /api/sharing/session
GET /api/sharing/session/{id}
WebSocket /api/sharing/session/{id}/ws
```

#### 3.8 Календарь просмотров
```python
POST /api/viewings/schedule
GET /api/viewings/my
PUT /api/viewings/{id}/reschedule
```

#### 3.9 Чат с арендодателем
```python
POST /api/messages
GET /api/messages/conversations
WebSocket /api/ws/messages
```

### 🟢 Низкий приоритет

#### 3.10 Виртуальные туры
```python
GET /api/properties/{id}/virtual-tour
POST /api/properties/{id}/virtual-tour/upload
```

#### 3.11 Документы и договоры
```python
POST /api/documents/contract/generate
GET /api/documents/{id}/sign
POST /api/documents/{id}/upload
```

#### 3.12 Платежи онлайн
```python
POST /api/payments/deposit
GET /api/payments/history
POST /api/payments/recurring
```

---

## 4. Улучшения существующих API

### 4.1 GraphQL API
Добавить полноценный GraphQL для гибких запросов:
```graphql
query {
  properties(
    city: "Москва",
    filters: { minPrice: 30000, maxPrice: 80000 }
  ) {
    id
    title
    price
    area
    location { lat, lon }
    photos { url, thumbnail }
    owner { name, phone }
  }
}
```

### 4.2 Версионирование API
```
/api/v1/properties
/api/v2/properties  ← с новыми фичами
```

### 4.3 Rate Limiting по ролям
```python
@rate_limit(tier="user", requests=100, window=60)
@rate_limit(tier="premium", requests=500, window=60)
@rate_limit(tier="admin", requests=10000, window=60)
```

### 4.4 Webhooks
```python
POST /api/webhooks
{
  "url": "https://example.com/webhook",
  "events": ["new_property", "price_drop"],
  "filters": {"city": "Москва"}
}
```

---

## 5. Приоритетный план развития

### Спринт 1 (1-2 недели)
- [ ] Парсер Etagi.com
- [ ] API сравнения объектов
- [ ] История цен и тренды
- [ ] Уведомления о снижении цены

### Спринт 2 (2-3 недели)
- [ ] Геолокация и heatmap
- [ ] Парсер Cian Commercial
- [ ] GraphQL API (базовый)
- [ ] Webhooks

### Спринт 3 (3-4 недели)
- [ ] Отзывы о домах
- [ ] Избранное с папками
- [ ] Парсер Росреестра
- [ ] Rate limiting по ролям

### Спринт 4+ (1-2 месяца)
- [ ] Чат с арендодателем
- [ ] Календарь просмотров
- [ ] Виртуальные туры
- [ ] Документы и договоры

---

## 6. Технические рекомендации

### 6.1 Мониторинг API
Добавить:
- Response time percentiles (p50, p95, p99)
- Error rate по endpoint'ам
- Rate limit hits
- Cache hit ratio

### 6.2 Документация
- Обновить OpenAPI spec
- Добавить примеры запросов/ответов
- Создать Postman коллекцию
- Добавить SDK для популярных языков

### 6.3 Тестирование
- Integration tests для всех endpoints
- Load testing с k6/Locust
- Contract testing
- Chaos engineering

### 6.4 Безопасность
- Rate limiting на всех публичных endpoints
- Input validation
- SQL injection prevention audit
- XSS/CSRF protection

---

## 7. Метрики для отслеживания

| Метрика | Текущее | Цель |
|---------|---------|------|
| API Response Time (p95) | <500ms | <200ms |
| Error Rate | <1% | <0.1% |
| Cache Hit Ratio | 70% | 90% |
| Parser Success Rate | 85% | 95% |
| Uptime | 99% | 99.9% |

---

## 8. Выводы

**Текущее состояние:** Проект имеет хорошо развитую API базу с 30+ endpoints, 10 рабочими парсерами, системой аутентификации, кешированием и мониторингом.

**Приоритеты:**
1. Добавить 2-3 новых источника (Etagi, Cian Commercial, Росреестр)
2. Реализовать сравнение объектов и историю цен
3. Добавить геолокацию и heatmap
4. Улучшить документацию и мониторинг

**Оценочное время реализации:** 6-8 недель для всех улучшений высокого приоритета.
