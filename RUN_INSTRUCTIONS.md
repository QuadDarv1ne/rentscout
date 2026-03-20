# RentScout — Инструкция по запуску

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
# Копирование примера
cp .env.example .env

# Генерация безопасных секретов
python scripts/generate_secrets.py
```

### 3. Запуск приложения

#### Вариант A: Uvicorn (рекомендуется для разработки)

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Вариант B: Docker

```bash
# Development
docker-compose -f docker-compose.dev.yml up -d

# Production
docker-compose up -d
```

### 4. Проверка работы

Откройте в браузере:

- **API Documentation**: http://localhost:8000/docs
- **Custom Docs**: http://localhost:8000/docs-custom
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/health
- **GraphQL**: http://localhost:8000/graphql

### 5. CLI утилита

```bash
# Просмотр помощи
python -m app.cli --help

# Статус сервисов
python -m app.cli status services

# Статистика кеша
python -m app.cli cache stats

# Статистика БД
python -m app.cli db stats
```

## 🔧 Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `APP_NAME` | Имя приложения | RentScout |
| `DEBUG` | Режим отладки | false |
| `LOG_LEVEL` | Уровень логов | INFO |
| `DATABASE_URL` | URL PostgreSQL | postgresql://... |
| `REDIS_URL` | URL Redis | redis://... |
| `SECRET_KEY` | Секретный ключ | (генерируется) |
| `JWT_SECRET` | JWT секрет | (генерируется) |

### Генерация секретов

```bash
python scripts/generate_secrets.py
```

Это создаст `.env` файл с криптографически стойкими паролями.

## 📊 Доступные эндпоинты

### Основные

| Endpoint | Описание |
|----------|----------|
| `GET /api` | Корневой endpoint |
| `GET /api/health` | Проверка здоровья |
| `GET /api/health/detailed` | Расширенная проверка |
| `GET /api/properties` | Поиск недвижимости |
| `POST /api/properties/advanced-search` | Расширенный поиск |
| `GET /api/db/properties` | CRUD операции |
| `GET /api/tasks` | Фоновые задачи |
| `GET /api/notifications` | Уведомления |
| `GET /api/bookmarks` | Закладки |
| `POST /api/ml/predict` | ML предсказания |

### Monitoring

| Endpoint | Описание |
|----------|----------|
| `GET /metrics` | Prometheus метрики |
| `GET /api/advanced-metrics` | Расширенные метрики |
| `GET /api/quality-metrics` | Метрики качества |
| `GET /api/system/inspect` | Информация о системе |

### GraphQL

```graphql
# Пример запроса
query {
    properties(limit: 10) {
        id
        title
        price
        rooms
        area
        city
    }
    
    statistics(city: "Москва") {
        total
        avgPrice
        minPrice
        maxPrice
    }
}
```

## 🐛 Решение проблем

### Ошибки кодировки на Windows

```bash
# Установить UTF-8 кодировку
chcp 65001

# Или запустить с PYTHONUTF8
set PYTHONUTF8=1
python -m uvicorn app.main:app
```

### Ошибки подключения к БД

```bash
# Запустить PostgreSQL
docker-compose -f docker-compose.dev.yml up postgres

# Применить миграции
alembic upgrade head
```

### Ошибки Redis

```bash
# Запустить Redis
docker-compose -f docker-compose.dev.yml up redis
```

## 📈 Мониторинг

### Prometheus

Откройте http://localhost:9091 (если запущен через Docker)

### Grafana

Откройте http://localhost:3001 (admin/admin)

### Логи

```bash
# Просмотр логов
tail -f logs/app.log

# Логи в Docker
docker-compose logs -f app
```

## 🎯 Production запуск

```bash
# С балансировщиком нагрузки
python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --loop uvloop \
    --http httptools
```

## 📝 Тестирование

```bash
# Запустить все тесты
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Конкретный тест
pytest app/tests/test_search_service.py -v
```

## 🎉 Готово!

Приложение запущено и готово к использованию!

**Основной URL**: http://localhost:8000  
**Документация**: http://localhost:8000/docs  
**GraphQL**: http://localhost:8000/graphql
