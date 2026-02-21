# 👋 Onboarding Guide для новых разработчиков RentScout

**Версия:** 2.3.0  
**Последнее обновление:** 21 февраля 2026 г.

---

## 📋 Оглавление

1. [Введение](#введение)
2. [Быстрый старт](#быстрый-старт)
3. [Настройка окружения](#настройка-окружения)
4. [Структура проекта](#структура-проекта)
5. [Первые шаги](#первые-шаги)
6. [Полезные команды](#полезные-команды)
7. [Ресурсы](#ресурсы)

---

## Введение

**RentScout** — это высокопроизводительный API для агрегации объявлений об аренде недвижимости.

### Что вы узнаете

- Как настроить окружение для разработки
- Как запустить проект локально
- Как запускать тесты
- Как вносить изменения в код
- Куда обращаться за помощью

### Технологии

| Категория | Технологии |
|-----------|------------|
| Язык | Python 3.9+ |
| Framework | FastAPI |
| База данных | PostgreSQL, Redis |
| Очереди | Celery |
| Контейнеры | Docker, Docker Compose |
| Мониторинг | Prometheus, Grafana, Sentry |

---

## Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/QuadDarv1ne/rentscout.git
cd rentscout
```

### 2. Установка зависимостей

```bash
# Создание виртуального окружения
python -m venv venv

# Активация (Windows)
venv\Scripts\activate

# Активация (Linux/Mac)
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Настройка окружения

```bash
# Копирование примера конфигурации
cp .env.example .env

# Генерация безопасных секретов
python scripts/generate_secrets.py
```

### 4. Запуск через Docker (рекомендуется)

```bash
# Запуск всех сервисов
make docker-up

# Или через docker-compose
docker-compose -f docker-compose.dev.yml up -d
```

### 5. Проверка

Откройте в браузере:
- **API Docs:** http://localhost:8000/docs
- **pgAdmin:** http://localhost:5050 (admin@admin.com / admin)
- **Redis Commander:** http://localhost:8081

---

## Настройка окружения

### Необходимое ПО

| Программа | Версия | Ссылка |
|-----------|--------|--------|
| Python | 3.9+ | [python.org](https://python.org) |
| Docker | 24+ | [docker.com](https://docker.com) |
| Git | 2.x | [git-scm.com](https://git-scm.com) |
| Make | 4.x | (обычно предустановлен) |

### Опциональное ПО

| Программа | Назначение |
|-----------|------------|
| VS Code | Редактор кода |
| PostgreSQL | Локальная БД (если не через Docker) |
| Redis | Локальный кэш (если не через Docker) |
| DBeaver | GUI для работы с БД |

### Переменные окружения

**Минимальный набор для разработки:**

```env
# Application
APP_NAME=RentScout
DEBUG=true
LOG_LEVEL=DEBUG

# Security (сгенерируйте скриптом!)
SECRET_KEY=<64+ символов>
JWT_SECRET=<64+ символов>

# Database
DATABASE_URL=postgresql+asyncpg://rentscout:rentscout_dev_password@localhost:5432/rentscout
REDIS_URL=redis://localhost:6379/0

# Development
TESTING=false
HOT_RELOAD=true
```

---

## Структура проекта

```
rentscout/
├── 📁 app/                    # Основное приложение
│   ├── 📁 api/                # API endpoint'ы
│   │   ├── endpoints/         # Текущие endpoint'ы
│   │   ├── v1/                # Версия API v1
│   │   └── router_registration.py
│   ├── 📁 core/               # Ядро (config, security)
│   ├── 📁 db/                 # База данных
│   │   ├── models/            # SQLAlchemy модели
│   │   └── repositories/      # Доступ к данным
│   ├── 📁 parsers/            # Парсеры
│   ├── 📁 services/           # Бизнес-логика
│   ├── 📁 tasks/              # Celery задачи
│   ├── 📁 utils/              # Утилиты
│   ├── 📁 ml/                 # ML модели
│   ├── 📁 middleware/         # Middleware
│   └── main.py                # Точка входа
│
├── 📁 tests/                  # Тесты
│   ├── integration/           # Интеграционные тесты
│   ├── test_auth.py           # Тесты аутентификации
│   ├── test_ml.py             # Тесты ML
│   └── ...
│
├── 📁 docker/                 # Docker конфигурации
│   ├── nginx/
│   ├── prometheus/
│   └── grafana/
│
├── 📁 docs/                   # Документация
│   ├── ARCHITECTURE.md        # Архитектура
│   ├── API_EXAMPLES.md        # Примеры API
│   ├── SENTRY_SETUP.md        # Sentry
│   └── SECURITY_AUDIT.md      # Безопасность
│
├── 📁 scripts/                # Скрипты
│   ├── generate_secrets.py    # Генерация секретов
│   └── ...
│
├── 📄 docker-compose.yml      # Production Docker
├── 📄 docker-compose.dev.yml  # Development Docker
├── 📄 Makefile                # Команды Make
├── 📄 requirements.txt        # Зависимости Python
├── 📄 pyproject.toml          # Конфигурация проекта
└── 📄 README.md               # Главная документация
```

---

## Первые шаги

### 1. Запуск приложения

```bash
# Вариант 1: Через Make (рекомендуется)
make dev

# Вариант 2: Напрямую
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Запуск тестов

```bash
# Все тесты
make test

# Тесты с покрытием
make test-coverage

# Конкретный файл
pytest tests/test_auth.py -v
```

### 3. Применение миграций

```bash
# Применить все миграции
make db-migrate

# Или напрямую
alembic upgrade head
```

### 4. Создание новой фичи

```bash
# Создайте новую ветку
git checkout -b feature/your-feature-name

# Внесите изменения
# ...

# Запустите тесты
make test

# Закоммитьте изменения
git add .
git commit -m "feat: описание изменений"

# Отправьте в репозиторий
git push origin feature/your-feature-name
```

---

## Полезные команды

### Разработка

```bash
make dev              # Запуск dev сервера
make docker-up        # Запуск Docker сервисов
make docker-logs      # Просмотр логов
make db-shell         # Подключение к БД
```

### Тестирование

```bash
make test             # Запуск тестов
make test-coverage    # Тесты с покрытием
make test-fast        # Быстрые тесты
make test-integration # Интеграционные тесты
```

### Code Quality

```bash
make lint             # Запуск линтеров
make lint-fix         # Авто-исправление
make format           # Форматирование кода
make type-check       # Проверка типов
make security-check   # Проверка безопасности
```

### Docker

```bash
make docker-build     # Сборка образов
make docker-rebuild   # Пересборка и перезапуск
make docker-clean     # Очистка Docker
```

---

## Внесение изменений

### 1. Создание endpoint'а

**Файл:** `app/api/endpoints/your_feature.py`

```python
from fastapi import APIRouter, Depends
from typing import List

router = APIRouter(prefix="/your-feature", tags=["your-feature"])

@router.get("/")
async def get_items():
    """Получить список элементов."""
    return {"items": []}

@router.post("/")
async def create_item(item: ItemCreate):
    """Создать новый элемент."""
    return {"id": 1, **item.dict()}
```

**Регистрация:** `app/api/router_registration.py`

```python
from app.api.endpoints import your_feature

def register_all_routers(app: FastAPI) -> None:
    # ...
    app.include_router(your_feature.router, prefix="/api", tags=["your-feature"])
```

### 2. Создание модели БД

**Файл:** `app/db/models/your_model.py`

```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.session import Base

class YourModel(Base):
    __tablename__ = "your_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
```

**Миграция:**

```bash
alembic revision --autogenerate -m "Add your_model table"
alembic upgrade head
```

### 3. Создание Celery задачи

**Файл:** `app/tasks/your_tasks.py`

```python
from app.tasks.celery import celery
from app.utils.logger import logger

@celery.task
def your_background_task(param: str):
    """Фоновая задача."""
    logger.info(f"Running task with {param}")
    # Ваша логика
    return {"status": "success"}
```

---

## Ресурсы

### Документация

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектура системы |
| [API_EXAMPLES.md](API_EXAMPLES.md) | Примеры запросов API |
| [SECURITY_AUDIT.md](SECURITY_AUDIT.md) | Аудит безопасности |
| [SENTRY_SETUP.md](SENTRY_SETUP.md) | Настройка Sentry |
| [RUNBOOK.md](RUNBOOK.md) | Действия при инцидентах |

### Внешние ресурсы

| Ресурс | Описание |
|--------|----------|
| [FastAPI Docs](https://fastapi.tiangolo.com/) | Официальная документация FastAPI |
| [SQLAlchemy Docs](https://docs.sqlalchemy.org/) | Документация SQLAlchemy |
| [Celery Docs](https://docs.celeryq.dev/) | Документация Celery |
| [Docker Docs](https://docs.docker.com/) | Документация Docker |

### Контакты

| Канал | Описание |
|-------|----------|
| GitHub Issues | Баг-репорты и фичи |
| Email | support@rentscout.dev |
| Slack/Discord | (ссылка в README) |

---

## Чеклист нового разработчика

- [ ] Склонировал репозиторий
- [ ] Установил Python 3.9+
- [ ] Установил Docker
- [ ] Сгенерировал секреты (`python scripts/generate_secrets.py`)
- [ ] Запустил Docker сервисы (`make docker-up`)
- [ ] Открыл http://localhost:8000/docs
- [ ] Запустил тесты (`make test`)
- [ ] Прочитал [ARCHITECTURE.md](ARCHITECTURE.md)
- [ ] Создал первую фичу/багфикс

---

## FAQ

### ❓ Как отладить парсер?

```bash
# Запустите парсер напрямую
python -m app.parsers.avito.avito_parser

# Или через Python shell
python
>>> from app.parsers.avito import AvitoParser
>>> parser = AvitoParser()
>>> await parser.parse()
```

### ❓ Где смотреть логи?

```bash
# Логи приложения
make logs-tail

# Логи Docker
make docker-logs

# Логи Celery
docker logs rentscout-celery-worker -f
```

### ❓ Как сбросить базу данных?

```bash
# Полная очистка и миграция
make db-reset

# Или вручную
docker exec -it rentscout-postgres psql -U rentscout -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
alembic upgrade head
```

### ❓ Тесты падают с ошибкой подключения к БД

Проверьте что Docker сервисы запущены:

```bash
make docker-up
docker ps  # проверьте что postgres и redis работают
```

---

**Добро пожаловать в команду! 🚀**
