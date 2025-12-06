# 📚 Руководство разработчика RentScout

## Оглавление
1. [Архитектура](#архитектура)
2. [Установка окружения](#установка-окружения)
3. [Структура проекта](#структура-проекта)
4. [Запуск разработки](#запуск-разработки)
5. [Добавление нового парсера](#добавление-нового-парсера)
6. [Тестирование](#тестирование)
7. [Деплой](#деплой)
8. [Лучшие практики](#лучшие-практики)

---

## Архитектура

### Общая схема

```
Client → FastAPI → Router → Service → Parser → Database (Elasticsearch)
                               ↓
                             Cache (Redis)
```

### Слои приложения

| Слой | Описание | Файлы |
|------|----------|-------|
| **API Layer** | REST endpoints, валидация | `app/api/endpoints/` |
| **Service Layer** | Бизнес-логика поиска и фильтрации | `app/services/` |
| **Parser Layer** | Парсеры для разных площадок | `app/parsers/` |
| **Data Layer** | Взаимодействие с БД и кешем | `app/db/` |
| **Utils Layer** | Логирование, метрики, обработка ошибок | `app/utils/` |

---

## Установка окружения

### Требования
- Python 3.9+
- Docker и Docker Compose
- Redis (в контейнере или локально)
- Elasticsearch (в контейнере или локально)

### Локальная установка (без Docker)

```bash
# Клонировать репозиторий
git clone https://github.com/QuadDarv1ne/rentscout.git
cd rentscout

# Создать виртуальное окружение
python -m venv venv

# Активировать окружение
# На Windows:
.\venv\Scripts\Activate.ps1
# На Linux/Mac:
source venv/bin/activate

# Установить зависимости
pip install -r requirements-dev.txt

# Создать файл .env
cp .env.example .env  # Если файл существует
# или создать вручную с переменными:
# REDIS_URL=redis://localhost:6379/0
# ELASTICSEARCH_URL=http://localhost:9200
```

### Установка с Docker

```bash
docker-compose up --build
```

Это запустит:
- FastAPI приложение на http://localhost:8000
- Prometheus на http://localhost:9090
- Nginx на http://localhost:80
- Redis и Elasticsearch в фоне

---

## Структура проекта

```
rentscout/
├── app/
│   ├── api/                          # REST API endpoints
│   │   ├── endpoints/
│   │   │   ├── health.py            # Health check
│   │   │   └── properties.py        # Поиск недвижимости
│   │   └── deps.py                   # Зависимости (dependency injection)
│   │
│   ├── core/
│   │   ├── config.py                # Конфигурация приложения
│   │   └── security.py              # Безопасность, JWT (если используется)
│   │
│   ├── db/
│   │   ├── crud.py                  # CRUD операции
│   │   ├── elastic.py               # Клиент Elasticsearch
│   │   └── models/
│   │       └── session.py           # Сессии БД
│   │
│   ├── models/
│   │   └── schemas.py               # Pydantic схемы валидации
│   │
│   ├── parsers/                     # Парсеры площадок
│   │   ├── base_parser.py           # Базовый класс парсера
│   │   ├── avito/                   # Парсер Avito
│   │   ├── cian/                    # Парсер Cian
│   │   ├── ostrovok/                # Парсер Ostrovok
│   │   ├── sutochno/                # Парсер Sutochno
│   │   ├── tvil/                    # Парсер Tvil
│   │   ├── otello/                  # Парсер Otello
│   │   └── yandex_travel/           # Парсер Yandex.Travel
│   │
│   ├── services/                    # Бизнес-логика
│   │   ├── search.py                # Сервис поиска
│   │   ├── filter.py                # Фильтрация результатов
│   │   └── cache.py                 # Кеширование
│   │
│   ├── utils/                       # Утилиты
│   │   ├── error_handler.py         # Обработка ошибок
│   │   ├── logger.py                # Логирование
│   │   ├── metrics.py               # Метрики (Prometheus)
│   │   └── ratelimiter.py           # Ограничение частоты запросов
│   │
│   ├── tasks/
│   │   └── celery.py                # Celery задачи (если используется)
│   │
│   ├── tests/                       # Unit тесты
│   │   ├── conftest.py              # Pytest конфигурация
│   │   └── test_*.py                # Тестовые файлы
│   │
│   ├── main.py                      # Точка входа приложения
│   └── __init__.py
│
├── docker/                          # Docker конфигурация
│   ├── nginx/
│   │   └── nginx.conf               # Конфигурация Nginx
│   └── prometheus/
│       └── prometheus.yml           # Конфигурация Prometheus
│
├── docs/                            # Документация
│   ├── API.md                       # API документация
│   ├── METRICS.md                   # Метрики документация
│   └── DEV_GUIDE.md                 # Этот файл
│
├── scripts/                         # Вспомогательные скрипты
│   ├── db_seed.py                   # Инициализация БД
│   ├── deploy.sh                    # Развертывание
│   ├── dev_server.py                # Локальный сервер
│   └── run_tests.py                 # Запуск тестов
│
├── requirements.txt                 # Production зависимости
├── requirements-dev.txt             # Development зависимости
├── requirements-test.txt            # Testing зависимости
├── pyproject.toml                   # Конфигурация tools (black, mypy, isort)
├── docker-compose.yml               # Docker Compose конфигурация
└── README.md                        # Основная документация
```

---

## Запуск разработки

### Локально без Docker

```bash
# 1. Убедиться, что Redis и Elasticsearch запущены
# Если они локальные, запустить в отдельных терминалах:
redis-server
# и
elasticsearch

# 2. Запустить приложение
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### С Docker Compose

```bash
# Запустить все сервисы
docker-compose up -d

# Просмотреть логи
docker-compose logs -f api

# Остановить
docker-compose down
```

### Отладка

```python
# Используйте встроенный логгер
from app.utils.logger import logger

logger.info("Информационное сообщение")
logger.error("Сообщение об ошибке", exc_info=True)
```

---

## Добавление нового парсера

### Шаг 1: Создать папку парсера

```bash
mkdir -p app/parsers/mynewsite/
touch app/parsers/mynewsite/__init__.py
```

### Шаг 2: Реализовать базовый парсер

```python
# app/parsers/mynewsite/parser.py
from app.parsers.base_parser import BaseParser
from app.models.schemas import Property
from typing import List
from app.utils.logger import logger

class MyNewSiteParser(BaseParser):
    """Парсер для MyNewSite."""
    
    def __init__(self):
        super().__init__(name="mynewsite", base_url="https://mynewsite.com")
    
    async def parse(self, city: str, **filters) -> List[Property]:
        """Парсить объявления."""
        logger.info(f"Parsing {self.name} for {city}")
        
        try:
            # Ваша логика парсинга
            properties = []
            
            # Пример парсинга
            response = await self.session.get(
                f"{self.base_url}/search",
                params={"city": city, **filters}
            )
            
            # Обработка результатов
            data = response.json()
            for item in data.get("listings", []):
                prop = Property(
                    id=item["id"],
                    title=item["title"],
                    price=item["price"],
                    # ... остальные поля
                )
                properties.append(prop)
            
            return properties
            
        except Exception as e:
            logger.error(f"Error parsing {self.name}: {e}", exc_info=True)
            return []
```

### Шаг 3: Зарегистрировать парсер

```python
# app/services/search.py
from app.parsers.mynewsite.parser import MyNewSiteParser

class SearchService:
    def __init__(self):
        self.parsers = {
            "mynewsite": MyNewSiteParser(),
            # ... остальные парсеры
        }
```

### Шаг 4: Добавить тесты

```python
# app/tests/test_mynewsite_parser.py
import pytest
from app.parsers.mynewsite.parser import MyNewSiteParser

@pytest.mark.asyncio
async def test_mynewsite_parser():
    parser = MyNewSiteParser()
    results = await parser.parse("Москва")
    assert isinstance(results, list)
    assert len(results) > 0
```

---

## Тестирование

### Запуск тестов

```bash
# Все тесты
pytest

# Тесты конкретного файла
pytest app/tests/test_search_service.py

# С покрытием
pytest --cov=app --cov-report=html

# Конкретный тест
pytest app/tests/test_search_service.py::test_search_service_initialization

# Verbose режим
pytest -v
```

### Написание тестов

```python
# app/tests/test_example.py
import pytest
from unittest.mock import Mock, AsyncMock, patch

@pytest.fixture
def sample_data():
    """Фикстура для данных."""
    return {"name": "Test Property"}

@pytest.mark.asyncio
async def test_async_function(sample_data):
    """Тест асинхронной функции."""
    result = await some_async_function(sample_data)
    assert result is not None

def test_sync_function(sample_data):
    """Тест синхронной функции."""
    result = some_sync_function(sample_data)
    assert result == expected_value
```

### Конфигурация pytest

```python
# app/tests/conftest.py
import pytest
from app.models.schemas import Property

@pytest.fixture
def sample_property():
    return Property(
        id="test_123",
        title="Test Property",
        price=50000,
        # ... остальные поля
    )
```

---

## Деплой

### На сервер

```bash
# 1. SSH на сервер
ssh user@server.com

# 2. Клонировать репозиторий
git clone https://github.com/QuadDarv1ne/rentscout.git
cd rentscout

# 3. Запустить Docker Compose
docker-compose up -d

# 4. Проверить статус
docker-compose ps
curl http://localhost:8000/api/health
```

### Переменные окружения

Создайте `.env` файл:

```env
# App
APP_NAME=RentScout
LOG_LEVEL=INFO

# Redis
REDIS_URL=redis://redis:6379/0

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200

# Parsers
PROXY_ENABLED=false
CIAN_MAX_RETRIES=3
AVITO_RATE_LIMIT=5
RATE_LIMIT_WINDOW=60

# Security (если используется)
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

---

## Лучшие практики

### Кодирование

1. **Type Hints** - всегда используйте типизацию
   ```python
   async def parse(self, city: str) -> List[Property]:
       pass
   ```

2. **Документация** - добавляйте docstrings
   ```python
   def my_function(param: str) -> int:
       """Описание функции.
       
       Args:
           param: Описание параметра
           
       Returns:
           Описание возвращаемого значения
       """
       pass
   ```

3. **Логирование** - логируйте события
   ```python
   logger.info(f"Processing city: {city}")
   logger.error(f"Error occurred: {e}", exc_info=True)
   ```

4. **Обработка ошибок**
   ```python
   try:
       # code
   except SpecificException as e:
       logger.error(f"Specific error: {e}")
       raise
   except Exception as e:
       logger.error(f"Unexpected error: {e}", exc_info=True)
   ```

### Структура кода

1. **Следуйте PEP 8** - используйте black для форматирования
   ```bash
   black app/
   ```

2. **Используйте isort** для сортировки импортов
   ```bash
   isort app/
   ```

3. **Проверяйте типы с mypy**
   ```bash
   mypy app/
   ```

4. **Пишите тесты** - минимум 80% покрытия
   ```bash
   pytest --cov=app
   ```

### Git рабочий поток

```bash
# 1. Создать ветку для функции
git checkout -b feature/my-new-feature

# 2. Внести изменения и коммитить
git add .
git commit -m "Add: Description of changes"

# 3. Отправить ветку
git push origin feature/my-new-feature

# 4. Создать Pull Request на GitHub

# 5. После merge, удалить ветку
git checkout master
git pull
git branch -d feature/my-new-feature
```

### Коммит сообщения

Используйте convention commits:
- `feat:` - новая функция
- `fix:` - исправление ошибки
- `docs:` - изменение документации
- `style:` - форматирование кода
- `refactor:` - рефакторинг без изменения функциональности
- `perf:` - улучшение производительности
- `test:` - добавление тестов
- `chore:` - изменения конфигурации, зависимостей

Примеры:
```
feat: Add new Yandex.Travel parser
fix: Handle connection errors in Elasticsearch client
docs: Update API documentation
test: Add unit tests for filter service
```

---

## Полезные ссылки

- [FastAPI документация](https://fastapi.tiangolo.com/)
- [Pydantic документация](https://docs.pydantic.dev/)
- [Pytest документация](https://docs.pytest.org/)
- [Elasticsearch документация](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
- [Redis документация](https://redis.io/documentation)
- [Prometheus документация](https://prometheus.io/docs/)

---

## FAQ

### Q: Как добавить новый фильтр?
**A:** Добавьте параметр в `Property` схему в `app/models/schemas.py` и реализуйте логику фильтрации в `app/services/filter.py`.

### Q: Как дебагировать парсер?
**A:** Используйте `logger` для вывода информации и добавьте breakpoints в IDE.

### Q: Как обновить зависимости?
**A:** `pip install -U pip && pip install -r requirements-dev.txt`

### Q: Как запустить только интеграционные тесты?
**A:** `pytest app/tests/ -m integration`

---

**Последнее обновление:** Декабрь 2025
**Разработчик:** QuadDarv1ne
