# 🏠 RentScout – Парсер арендной недвижимости

[![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-red)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-✓-blue?logo=docker)](https://docker.com)

**RentScout** – это высокопроизводительный API для агрегации данных об аренде жилья с ведущих площадок.  

Собирает актуальную информацию, фильтрует дубликаты и предоставляет удобный интерфейс для интеграции.

## 🌟 Особенности

- **Поддержка 15+ фильтров**: город, метро, цена, тип жилья и др.
- **Парсинг данных в реальном времени** с Avito, Ostrovok и др.
- **Умное кеширование** результатов (Redis)
- **Мониторинг** метрик через Prometheus
- **Масштабируемая архитектура** на Docker
- **Автоматическая документация** Swagger/OpenAPI

## 🚀 Быстрый старт

### Установка через `Docker`

  ```bash
  git clone https://github.com/yourname/rentscout.git
  cd rentscout
  docker-compose up --build
  ```

`API` будет доступно на `http://localhost:8000`

**Документация:** `http://localhost:8000/docs`

### 🛠 Пример использования

**Поиск квартир в Москве:**

```http
GET /api/properties?city=Москва&property_type=Квартира&price_max=5000
```

**Ответ:**

  ```json
  [
    {
      "source": "Avito",
      "title": "2-комн. квартира, 45 м²",
      "price": 3500,
      "area": 45,
      "rooms": 2,
      "link": "https://avito.ru/...",
      "photo": "https://img.avito.ru/..."
    }
  ]
  ```

### 📊 Технологии

- **Backend:** `FastAPI`, `Redis`, `Celery`
- **Парсинг:** `BeautifulSoup4`, `httpx`, `Playwright`
- **Инфраструктура:** `Docker`, `Prometheus`, `Nginx`
- **Аналитика:** `Pandas`, `Elasticsearch`

### 📚 API Endpoints

Метод | Путь               | Описание
GET	  | /api/properties	   | Поиск недвижимости
POST  | /api/subscriptions | Уведомления о новых объявлениях
GET	  | /health	           | Проверка статуса API

### Полная структура проекта

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
│   │   │   └── health.py     # Health-check и метрики
│   │   └── deps.py           # Общие зависимости (кеш, БД)
│   │
│   ├── core/                 # Ядро системы
│   │   ├── config.py         # Конфиг из переменных окружения
│   │   └── security.py       # JWT-аутентификация
│   ├── db/                   # Database Layer
│   │   ├── models/           # SQLAlchemy ORM-модели
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
│   │   └── otello/                   # https://otello.ru
│   │       ├── scraper.py            # Основной скрапер
│   │       └── session_manager.py    # Управление сессиями
│   │
│   ├── services/             # Business Logic
│   │   ├── cache.py          # Redis-кеш (LRU, TTL)
│   │   └── filter.py         # Фильтры и сортировка
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
│   │   └── metrics.py        # Prometheus метрики
│   └── main.py               # Точка входа
│ 
├── docker/                   # Docker конфиги
│   ├── nginx/
│   │   └── nginx.conf        # Конфиг балансировщика
│   └── prometheus/
│       └── prometheus.yml    # Настройки мониторинга
│ 
├── docs/                     # Документация
│   ├── API.md                # OpenAPI спецификация
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
