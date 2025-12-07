# 🚀 RentScout - Новые Возможности

## 📋 Обзор улучшений

Проект улучшен с добавлением production-ready функций для масштабирования и мониторинга.

---

## 1. 💾 Расширенное Redis Кеширование

### Возможности
- **Cache warming**: Автоматический прогрев кеша для популярных городов при старте
- **Метрики**: Отслеживание hit rate, cache misses, errors
- **Тегирование**: Группировка ключей кеша по тегам (source, city, parser)
- **Интеллектуальное удаление**: Очистка по паттернам и тегам

### API Endpoints
```http
GET /api/cache/stats
```

### Использование в коде
```python
from app.services.advanced_cache import cached_parser

@cached_parser(expire=600, source="avito")
async def parse(city: str):
    # Результат кешируется на 10 минут
    pass
```

### Конфигурация
```python
CACHE_TTL = 300  # 5 минут по умолчанию
REDIS_URL = "redis://localhost:6379/0"
```

---

## 2. 📝 Структурированное JSON Логирование

### Возможности
- **JSON формат**: Структурированные логи для production
- **Correlation IDs**: Отслеживание запросов через всю систему
- **Контекстные данные**: Автоматическое добавление metadata
- **Цветной вывод**: Читаемые логи для разработки

### Пример лога (JSON)
```json
{
  "timestamp": "2025-12-06T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.api.endpoints.properties",
  "message": "Search completed for Москва",
  "correlation_id": "a1b2c3d4-e5f6-7890",
  "duration": 1.234,
  "city": "Москва",
  "count": 42
}
```

### Использование
```python
from app.utils.structured_logger import logger

# Простое логирование
logger.info("Property search started", city=city, filters=filters)

# Специализированные методы
logger.log_request("GET", "/api/properties", 200, 0.5)
logger.log_parser_result("avito", "Москва", 42, 1.5, success=True)
logger.log_cache_operation("get", hit=True, key="parser:avito:moscow")
```

---

## 3. 🚦 Rate Limiting по IP

### Возможности
- **Двойная защита**: Main limit + burst protection
- **Whitelist**: Доверенные IP без ограничений
- **X-RateLimit-* заголовки**: Информация о лимитах в ответах
- **HTTP 429**: Автоматический возврат при превышении

### Лимиты по умолчанию
- **Main**: 100 запросов / 60 секунд
- **Burst**: 10 запросов / 1 секунда
- **Whitelist**: 127.0.0.1, ::1, localhost

### API Endpoints
```http
GET /api/ratelimit/stats
```

### Response Headers
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1733482800
```

### Конфигурация
```python
API_RATE_LIMIT = 100  # Запросов в минуту
```

---

## 4. ⚡ Celery фоновые задачи

### Возможности
- **Асинхронный парсинг**: Запуск парсинга в фоне
- **Пакетный парсинг**: Обработка нескольких городов сразу
- **Периодические задачи**: Автообновление через Celery Beat
- **Cache warming**: Автоматический прогрев кеша

### API Endpoints

#### Запуск парсинга
```http
POST /api/tasks/parse
Content-Type: application/json

{
  "city": "Москва",
  "property_type": "Квартира"
}
```

Response:
```json
{
  "task_id": "abc123-def456",
  "status": "queued",
  "city": "Москва"
}
```

#### Пакетный парсинг
```http
POST /api/tasks/parse/batch
Content-Type: application/json

{
  "cities": ["Москва", "Казань", "Сочи"],
  "property_type": "Квартира"
}
```

#### Запланированный парсинг
```http
POST /api/tasks/parse/schedule
Content-Type: application/json

{
  "city": "Москва",
  "property_type": "Квартира",
  "eta_seconds": 3600
}
```

#### Проверка статуса задачи
```http
GET /api/tasks/{task_id}
```

Response:
```json
{
  "task_id": "abc123",
  "status": "SUCCESS",
  "ready": true,
  "successful": true,
  "result": {
    "status": "success",
    "city": "Москва",
    "count": 42,
    "properties": [...]
  }
}
```

#### Отмена задачи
```http
DELETE /api/tasks/{task_id}
```

### Периодические задачи

Автоматически запускаются через Celery Beat:

| Задача | Расписание | Описание |
|--------|-----------|----------|
| `warm-cache-popular-cities` | Каждые 30 минут | Прогрев кеша для популярных городов |
| `cleanup-old-cache` | 3:00 каждый день | Очистка старого кеша |
| `update-top-cities` | Каждый час | Обновление данных топ-5 городов |

### Запуск Celery Worker

```bash
# Worker для выполнения задач
celery -A app.tasks.celery worker --loglevel=info

# Beat для периодических задач
celery -A app.tasks.celery beat --loglevel=info

# Все вместе
celery -A app.tasks.celery worker --beat --loglevel=info
```

### Мониторинг через Flower

```bash
pip install flower
celery -A app.tasks.celery flower
# Открыть http://localhost:5555
```

---

## 📊 Статистика и Мониторинг

### Health Endpoints

```http
GET /api/health          # Простая проверка
GET /api/health/detailed # Подробная информация
GET /api/stats           # Общая статистика + кеш
GET /api/cache/stats     # Детальная статистика кеша
GET /api/ratelimit/stats # Статистика rate limiting
```

### Prometheus Metrics

Доступны по адресу `/metrics`:
- Request duration
- Request count
- Cache hit rate
- Parser errors
- Active requests

---

## 🔧 Настройка окружения

### Обновленные зависимости

```bash
pip install -r requirements.txt
```

Новые пакеты:
- `celery[redis]>=5.3.0` - Фоновые задачи
- `redis` - Кеширование

### Переменные окружения

```env
# Redis
REDIS_URL=redis://localhost:6379/0

# Кеширование
CACHE_TTL=300

# Rate Limiting
API_RATE_LIMIT=100

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Docker Compose

Добавьте Redis в `docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  celery_worker:
    build: .
    command: celery -A app.tasks.celery worker --loglevel=info
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/0

  celery_beat:
    build: .
    command: celery -A app.tasks.celery beat --loglevel=info
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/0

volumes:
  redis_data:
```

---

## 🧪 Тестирование

Все новые функции покрыты тестами:

```bash
# Все тесты
pytest

# Конкретные модули
pytest app/tests/test_advanced_cache.py
pytest app/tests/test_structured_logger.py
pytest app/tests/test_ip_ratelimiter.py
pytest app/tests/test_celery_tasks.py

# С покрытием
pytest --cov=app --cov-report=html
```

### Статистика тестов

- **Всего тестов**: 193 ✅
- **Advanced Cache**: 1/11 (остальные требуют Redis)
- **Structured Logger**: 9/9 ✅
- **IP Rate Limiter**: 9/9 ✅
- **Celery Tasks**: 13/13 ✅
- **Остальные**: 161/161 ✅

---

## 📈 Production Checklist

- [ ] Redis настроен и доступен
- [ ] Celery worker запущен
- [ ] Celery beat запущен (для периодических задач)
- [ ] Prometheus metrics включены
- [ ] JSON логирование активировано
- [ ] Rate limits настроены для production
- [ ] Cache warming cities настроены
- [ ] Whitelist IP обновлен
- [ ] Correlation IDs логируются
- [ ] Мониторинг и алерты настроены

---

## 📡 Monitoring & Alerts (Prometheus)

- **Метрики**: `/metrics` (Prometheus client + MetricsMiddleware)
- **Scrape targets**: `web:8000` и `localhost:8000` (для локальной разработки)
- **Alert rules**: `docker/prometheus/alerts.yml`

### Запуск Prometheus

```bash
docker-compose up -d prometheus
```

Prometheus будет доступен на `http://localhost:9090`.

### Настроенные алерты

- `HighErrorRate`: >5% 5xx за 5 минут
- `HighLatencyP95`: p95 > 2s за 5 минут
- `TooManyActiveRequests`: >50 активных запросов 2 минуты
- `ParserFailures`: >5 ошибок парсеров за 10 минут

---

**Версия**: 2.0.0  
**Дата обновления**: 6 декабря 2025  
**Статус**: ✅ Production Ready
