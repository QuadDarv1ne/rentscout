# 🏠 RentScout – Парсер арендной недвижимости

[![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-red)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-✓-blue?logo=docker)](https://docker.com)

**RentScout** – это высокопроизводительный API для агрегации данных об аренде жилья с ведущих площадок.  

Собирает актуальную информацию, фильтрует дубликаты и предоставляет удобный интерфейс для интеграции.

## 🌟 Особенности

- **Поддержка 15+ фильтров**: цена (мин/макс), количество комнат (мин/макс), площадь (мин/макс), тип жилья и др.
- **Парсинг данных в реальном времени** с Avito, Cian, Domofond, Yandex Realty и других площадок
- **Умное кеширование** результатов (Redis)
- **Мониторинг** метрик через Prometheus
- **Масштабируемая архитектура** на Docker
- **Автоматическая документация** Swagger/OpenAPI
- **Ограничение частоты запросов** для предотвращения блокировки
- **Сохранение данных** в PostgreSQL
- **Расширенная система метрик** для мониторинга производительности
- **Улучшенная обработка ошибок** с повторными попытками
- **Поддержка множества источников** - Avito, Cian, Domofond, Yandex Realty и другие

## 🚀 Быстрый старт

> **⚡ Самый быстрый способ**: См. [QUICKSTART.md](QUICKSTART.md)

### Способ 1: Автоматический (рекомендуется)

```bash
python scripts/start.py
```

### Способ 2: Docker Compose

```bash
git clone https://github.com/QuadDarv1ne/rentscout.git
cd rentscout
docker-compose -f docker-compose.dev.yml up --build
```

### Способ 3: Локальный запуск

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

`API` будет доступно на `http://localhost:8000`

**Документация:** `http://localhost:8000/docs`

> 📘 **Проблемы?** См. [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## 🛠 Примеры использования

### Поиск квартир в Москве с фильтрацией:

```http
GET /api/properties?city=Москва&property_type=Квартира&min_price=3000&max_price=8000&min_rooms=1&max_rooms=3&min_area=30&max_area=80
```

**Ответ:**

```json
[
  {
    "id": 12345678,
    "source": "avito",
    "external_id": "987654321",
    "title": "2-комн. квартира, 45 м², ЦАО",
    "description": "Сдается 2-комнатная квартира в центре Москвы",
    "link": "https://www.avito.ru/moskva/sdam/na_sutki/...",
    "price": 5000,
    "currency": "RUB",
    "price_per_sqm": 111.11,
    "rooms": 2,
    "area": 45,
    "floor": 3,
    "total_floors": 9,
    "city": "Москва",
    "district": "Центральный",
    "address": "ул. Тверская, 10",
    "latitude": 55.7558,
    "longitude": 37.6176,
    "location": {
      "city": "Москва",
      "district": "Центральный",
      "address": "ул. Тверская, 10"
    },
    "photos": [
      "https://img.avito.ru/...",
      "https://img.avito.ru/..."
    ],
    "features": {
      "wifi": true,
      "parking": false,
      "furniture": true
    },
    "contact_name": "Иван Петров",
    "contact_phone": "+7 (999) 123-45-67",
    "is_active": true,
    "is_verified": false,
    "first_seen": "2023-06-15T10:30:00",
    "last_seen": "2023-06-15T10:30:00",
    "created_at": "2023-06-15T10:30:00",
    "last_updated": "2023-06-15T10:30:00"
  }
]
```

### Поиск недорогого жилья в Санкт-Петербурге:

```http
GET /api/properties?city=Санкт-Петербург&max_price=5000&has_photos=true&sort_by=price_per_sqm&sort_order=asc
```

### Создание фоновой задачи парсинга:

```http
POST /api/tasks/parse
Content-Type: application/json

{
  "city": "Новосибирск",
  "property_type": "Квартира"
}
```

### Получение статистики по объявлениям:

```http
GET /api/properties/stats/overview?city=Москва
```

## 📊 Технологии

- **Backend:** `FastAPI`, `Redis`, `Celery`, `PostgreSQL`
- **Парсинг:** `BeautifulSoup4`, `httpx`, `Playwright`
- **Инфраструктура:** `Docker`, `Prometheus`, `Nginx`
- **Аналитика:** `Pandas`, `SQLAlchemy`

## 📚 API Endpoints

Метод | Путь | Описание
------|------|---------
GET | /api/properties | Поиск недвижимости в реальном времени
GET | /api/properties/ | Поиск недвижимости в базе данных
POST | /api/properties/ | Создать объявление
GET | /api/properties/{id} | Получить объявление по ID
GET | /api/properties/stats/overview | Статистика объявлений
GET | /api/properties/stats/popular | Популярные объявления
POST | /api/tasks/parse | Создать задачу парсинга
GET | /api/tasks/{id} | Получить информацию о задаче
GET | /api/health | Проверка статуса API
GET | /api/health/detailed | Подробная проверка статуса API
GET | /api/stats | Статистика приложения
GET | /metrics | Метрики Prometheus

## 📈 Мониторинг и метрики

RentScout включает встроенную систему мониторинга на основе Prometheus, которая предоставляет метрики:

- **HTTP запросы**: количество, длительность, статусы
- **Парсеры**: количество вызовов, длительность выполнения
- **Активные запросы**: текущее количество обрабатываемых запросов
- **Кэш**: hit/miss ratio, использование памяти

Метрики доступны по адресу `/metrics`.

## Поддерживаемые источники

API поддерживает парсинг с следующих источников:
- Avito (https://www.avito.ru)
- CIAN (https://www.cian.ru)
- Domofond (https://domofond.ru)
- Yandex Realty (https://realty.yandex.ru)

## 📁 Полная структура проекта

```textline
rentscout/
│
├── .github/                  # GitHub Actions workflows
│   └── workflows/
│       ├── ci-cd.yml         # CI/CD: сборка, тесты, деплой
│       └── tests.yml         # Запуск юнит/интеграционных тестов
│ 
├── app/                      
│   ├── api/                  # API Layer
│   │   ├── endpoints/        
│   │   │   ├── properties.py # Роуты для работы с недвижимостью
│   │   │   ├── properties_db.py # Роуты для работы с БД
│   │   │   ├── tasks.py      # Роуты для фоновых задач
│   │   │   └── health.py     # Health-check и метрики
│   │   └── deps.py           # Общие зависимости (кеш, БД)
│   │
│   ├── core/                 # Ядро системы
│   │   ├── config.py         # Конфиг из переменных окружения
│   │   └── security.py       # JWT-аутентификация
│   ├── db/                   # Database Layer
│   │   ├── models/           # SQLAlchemy ORM-модели
│   │   ├── repositories/     # Репозитории для работы с данными
│   │   └── session.py        # Фабрика сессий БД
│   ├── models/               # Data Models
│   │   └── schemas.py        # Pydantic схемы для валидации
│   │
│   ├── parsers/                      # Парсеры (обновленная структура)
│   │   ├── sutochno/                 # https://sutochno.ru
│   │   │   ├── parser.py             # Основной парсер
│   │   │   ├── selectors.py          # CSS/XPath локаторы
│   │   │   └── schemas.py            # Нормализация данных
│   │   ├── ostrovok/                 # https://ostrovok.ru
│   │   │   ├── api_client.py         # Работа с REST API
│   │   │   └── models.py             # DTO для ответов API
│   │   ├── cian/                     # https://cian.ru
│   │   │   ├── parser.py             # Основной парсер
│   │   │   ├── selenium_parser.py    # Парсер с WebDriver
│   │   │   ├── anti_captcha.py       # Обход капчи
│   │   │   └── geo_utils.py          # Геокодирование
│   │   ├── avito/                    # https://www.avito.ru
│   │   │   ├── parser.py             # Основной парсер
│   │   │   └── phone_api.py          # Декодирование номеров
│   │   ├── yandex_travel/            # https://travel.yandex.ru
│   │   │   ├── api_connector.py      # Yandex API client
│   │   │   └── auth.py               # OAuth аутентификация
│   │   ├── tvil/                     # https://tvil.ru
│   │   │   ├── playwright_parser.py  # Парсер SPA
│   │   │   └── price_calendar.py     # Парсинг календаря цен
│   │   ├── otello/                   # https://otello.ru
│   │   │   ├── scraper.py            # Основной скрапер
│   │   │   └── session_manager.py    # Управление сессиями
│   │   ├── domofond/                 # https://domofond.ru
│   │   │   └── parser.py             # Основной парсер
│   │   └── yandex_realty/            # https://realty.yandex.ru
│   │       └── parser.py             # Основной парсер
│   │
│   ├── services/             # Business Logic
│   │   ├── cache.py          # Redis-кеш (LRU, TTL)
│   │   ├── advanced_cache.py # Расширенное кеширование
│   │   ├── filter.py         # Фильтры и сортировка
│   │   └── search.py         # Сервис поиска
│   ├── tasks/                # Фоновые задачи
│   │   └── celery.py         # Конфигурация Celery + Flower
│   ├── static/               # Статические файлы
│   │   ├── css/              # Стили (если есть фронт)
│   │   └── images/           # Логотипы и иконки
│   ├── templates/            # HTML шаблоны
│   │   └── email/            # Шаблоны писем
│   ├── tests/                # Тесты API
│   │   └── test_api.py       # Юнит-тесты
│   ├── utils/                # Вспомогательные модули
│   │   ├── logger.py         # Настройка логов
│   │   ├── metrics.py        # Prometheus метрики
│   │   ├── error_handler.py  # Обработка ошибок и повторные попытки
│   │   ├── ratelimiter.py    # Ограничение частоты запросов
│   │   ├── circuit_breaker.py # Защита от отказов
│   │   ├── retry.py          # Механизм повторных попыток
│   │   └── parser_errors.py  # Обработка ошибок парсинга
│   └── main.py               # Точка входа
│ 
├── docker/                   # Docker конфиги
│   ├── nginx/
│   │   └── nginx.conf        # Конфиг балансировщика
│   └── prometheus/
│       └── prometheus.yml    # Настройки мониторинга
│ 
├── docs/                     # Документация
│   ├── API.md                # Подробная OpenAPI спецификация
│   ├── METRICS.md            # Документация системы метрик
│   └── DEV_GUIDE.md          # Руководство разработчика
│ 
├── migrations/               # Миграции БД (Alembic)
│   └── versions/
│ 
├── scripts/                  # Вспомогательные скрипты
│   ├── deploy.sh             # Скрипт деплоя
│   └── db_seed.py            # Заполнение тестовыми данными
│ 
├── .dockerignore             # Игнорируемые файлы для Docker
├── .env.example              # Шаблон .env файла
├── .gitignore                # Игнорируемые файлы Git
├── alembic.ini               # Конфиг миграций
├── docker-compose.yml        # Оркестрация контейнеров
├── Dockerfile                # Сборка образа
├── LICENSE                   # Лицензия MIT
├── pyproject.toml            # Зависимости и настройки
├── README.md                 # Документация проекта
└── requirements.txt          # Список зависимостей
```

---

**Дата:** `20.04.2025`

**Преподаватель:** `Дуплей Максим Игоревич`

**Cоциальные сети:**

- **TG:** `@dupley_maxim_1999`
- **TG:** `@quadd4rv1n7`
- **VK:** `@maestro7it`