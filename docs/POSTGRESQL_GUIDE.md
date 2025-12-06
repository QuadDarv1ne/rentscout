# PostgreSQL Persistence Layer

Полноценный persistence слой для хранения данных о недвижимости в PostgreSQL с использованием SQLAlchemy 2.0 и Alembic для миграций.

## Архитектура

### Модели данных

Расположение: `app/db/models/property.py`

#### 1. Property (Основная таблица недвижимости)

```python
from app.db.models.property import Property
```

**Поля:**
- `id` - Автоинкрементный первичный ключ
- `source` - Источник данных (avito, cian и т.д.)
- `external_id` - ID объявления на источнике
- `title` - Заголовок объявления
- `description` - Описание
- `link` - Ссылка на объявление
- `price` - Цена аренды
- `currency` - Валюта (по умолчанию RUB)
- `price_per_sqm` - Цена за квадратный метр
- `rooms` - Количество комнат
- `area` - Площадь в кв.м
- `floor` / `total_floors` - Этаж
- `city` / `district` / `address` - Адрес
- `latitude` / `longitude` - Координаты
- `location` - JSON с полными данными о местоположении
- `photos` - JSON массив URL фотографий
- `features` - JSON с дополнительными характеристиками
- `contact_name` / `contact_phone` - Контакты
- `is_active` - Активно ли объявление
- `is_verified` - Прошло ли верификацию
- `first_seen` / `last_seen` - Временные метки
- `created_at` / `last_updated` - Временные метки

**Индексы:**
- Уникальный составной индекс по `(source, external_id)`
- Индексы по `city`, `price`, `is_active`
- Композитные индексы: `(city, price)`, `(source, city)`, `(is_active, price)`, `(rooms, area)`

#### 2. PropertyPriceHistory (История изменения цен)

Отслеживает все изменения цены для каждого объявления.

**Поля:**
- `property_id` - FK на Property
- `old_price` / `new_price` - Старая/новая цена
- `price_change` - Абсолютное изменение
- `price_change_percent` - Процентное изменение
- `changed_at` - Время изменения

#### 3. PropertyView (Просмотры объявлений)

Аналитика просмотров пользователями.

**Поля:**
- `property_id` - FK на Property
- `ip_address` - IP пользователя
- `user_agent` - User agent браузера
- `referer` - Откуда пришёл пользователь
- `viewed_at` - Время просмотра

#### 4. SearchQuery (Поисковые запросы)

Хранит поисковые запросы пользователей для аналитики.

**Поля:**
- `city`, `property_type` - Параметры поиска
- `min_price`, `max_price` - Диапазон цен
- `min_rooms`, `max_rooms` - Диапазон комнат
- `min_area`, `max_area` - Диапазон площади
- `query_params` - JSON с полными параметрами
- `results_count` - Количество результатов
- `ip_address`, `user_agent` - Метаданные пользователя

### Repository (CRUD операции)

Расположение: `app/db/repositories/property.py`

#### Основные операции

```python
from app.db.repositories import property as property_repo
from app.db.models.session import get_db

# Создание
property = await property_repo.create_property(db, property_data)

# Получение
property = await property_repo.get_property(db, property_id)
property = await property_repo.get_property_by_external_id(db, "avito", "123")

# Upsert (создание или обновление)
property, is_created = await property_repo.update_or_create_property(db, property_data)

# Поиск
properties = await property_repo.search_properties(
    db,
    city="Москва",
    min_price=30000,
    max_price=70000,
    min_rooms=2,
    max_rooms=3,
    limit=100
)

# Статистика
stats = await property_repo.get_property_statistics(db, city="Москва")
# Возвращает: total, avg_price, min_price, max_price, avg_area

# Bulk операции
result = await property_repo.bulk_upsert_properties(db, properties_list)
# Возвращает: {"created": N, "updated": M, "errors": K}

# Деактивация старых объявлений
count = await property_repo.deactivate_old_properties(db, source="avito", hours=24)
```

#### История цен

```python
# Отслеживание изменения цены
history = await property_repo.track_price_change(
    db, property_id, old_price=50000, new_price=55000
)

# Получение истории
history_list = await property_repo.get_price_history(db, property_id, limit=10)
```

#### Аналитика просмотров

```python
# Отслеживание просмотра
await property_repo.track_property_view(
    db, property_id,
    ip_address="192.168.1.1",
    user_agent="Mozilla/5.0"
)

# Получение количества просмотров
count = await property_repo.get_property_view_count(db, property_id, days=30)

# Популярные объявления
popular = await property_repo.get_popular_properties(db, limit=10, days=7)
# Возвращает: [(property_id, view_count), ...]
```

#### Аналитика поисков

```python
# Отслеживание поискового запроса
await property_repo.track_search_query(
    db,
    city="Москва",
    min_price=30000,
    max_price=70000,
    results_count=42
)

# Популярные запросы
searches = await property_repo.get_popular_searches(db, limit=10, days=7)
```

### Database Session

Расположение: `app/db/models/session.py`

#### Dependency Injection (для FastAPI)

```python
from app.db.models.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

@app.get("/items")
async def read_items(db: AsyncSession = Depends(get_db)):
    properties = await property_repo.search_properties(db)
    return properties
```

#### Context Manager

```python
from app.db.models.session import get_db_context

async with get_db_context() as db:
    result = await property_repo.get_property(db, 123)
```

#### Инициализация и закрытие

```python
from app.db.models.session import init_db, close_db

# Создать все таблицы (только для тестов!)
await init_db()

# Закрыть все соединения
await close_db()
```

## API Endpoints

Расположение: `app/api/endpoints/properties_db.py`

Базовый путь: `/api/db/properties`

### Основные endpoints

#### POST /api/db/properties/
Создать новое объявление.

**Request body:**
```json
{
  "source": "avito",
  "external_id": "123456",
  "title": "2-комн. квартира",
  "price": 50000,
  "rooms": 2,
  "area": 60,
  "location": {
    "city": "Москва",
    "address": "Тверская, 1"
  }
}
```

#### GET /api/db/properties/{property_id}
Получить объявление по ID.

#### GET /api/db/properties/
Поиск объявлений с фильтрами.

**Query параметры:**
- `city` - Город
- `source` - Источник (avito, cian)
- `min_price` / `max_price` - Диапазон цен
- `min_rooms` / `max_rooms` - Диапазон комнат
- `min_area` / `max_area` - Диапазон площади
- `is_active` - Только активные (default: true)
- `limit` - Макс. результатов (1-1000, default: 100)
- `offset` - Сдвиг для пагинации

**Пример:**
```bash
GET /api/db/properties/?city=Москва&min_price=30000&max_price=70000&min_rooms=2&limit=50
```

### Статистика

#### GET /api/db/properties/stats/overview
Общая статистика по объявлениям.

**Query параметры:**
- `city` - Фильтр по городу
- `source` - Фильтр по источнику

**Response:**
```json
{
  "total": 1234,
  "avg_price": 52340.5,
  "min_price": 15000,
  "max_price": 150000,
  "avg_area": 58.3
}
```

#### GET /api/db/properties/stats/popular
Топ популярных объявлений по просмотрам.

**Query параметры:**
- `limit` - Количество (1-100, default: 10)
- `days` - За сколько дней (1-365, default: 7)

#### GET /api/db/properties/stats/searches
Популярные поисковые запросы.

**Query параметры:**
- `limit` - Количество (1-100, default: 10)
- `days` - За сколько дней (1-365, default: 7)

### Аналитика

#### POST /api/db/properties/{property_id}/view
Отследить просмотр объявления.

Автоматически извлекает IP, user-agent и referer из запроса.

#### GET /api/db/properties/{property_id}/price-history
История изменения цены.

**Query параметры:**
- `limit` - Количество записей (1-100, default: 10)

### Bulk операции

#### POST /api/db/properties/bulk
Массовое создание/обновление объявлений.

**Request body:**
```json
[
  {
    "source": "avito",
    "external_id": "123",
    "title": "Квартира 1",
    "price": 50000
  },
  {
    "source": "avito",
    "external_id": "124",
    "title": "Квартира 2",
    "price": 60000
  }
]
```

**Response:**
```json
{
  "created": 15,
  "updated": 5,
  "errors": 0
}
```

#### POST /api/db/properties/deactivate-old
Деактивировать старые объявления.

**Query параметры:**
- `source` - Источник (обязательно)
- `hours` - Не видели дольше N часов (1-720, default: 24)

## Миграции (Alembic)

### Конфигурация

`alembic.ini` - Основной конфигурационный файл
`alembic/env.py` - Среда выполнения миграций
`alembic/versions/` - Директория с миграциями

### Команды

```bash
# Создать новую миграцию (автогенерация)
alembic revision --autogenerate -m "Add new field"

# Применить все миграции
alembic upgrade head

# Откатить одну миграцию
alembic downgrade -1

# Просмотр истории
alembic history

# Текущая версия
alembic current
```

### Первая миграция

Уже создана: `2025_12_06_0000-001_initial_initial_schema_with_property_models.py`

Создаёт все 4 таблицы с индексами.

## Конфигурация

### Environment Variables

Добавлено в `app/core/config.py`:

```python
DATABASE_URL: str = Field(
    default="postgresql+asyncpg://postgres:postgres@localhost:5432/rentscout",
    description="URL для подключения к PostgreSQL"
)
TESTING: bool = Field(default=False, description="Режим тестирования")
```

### Docker Compose

Добавьте PostgreSQL в `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: rentscout
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### .env файл

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/rentscout
```

## Интеграция с парсерами

Пример сохранения результатов парсинга:

```python
from app.parsers.avito.parser import AvitoParser
from app.db.repositories import property as property_repo
from app.db.models.session import get_db_context

# Парсинг
parser = AvitoParser()
raw_properties = await parser.parse(city="Москва", property_type="Квартира")

# Сохранение в PostgreSQL
async with get_db_context() as db:
    result = await property_repo.bulk_upsert_properties(db, raw_properties)
    print(f"Created: {result['created']}, Updated: {result['updated']}")
    
    # Деактивация старых
    count = await property_repo.deactivate_old_properties(db, "avito", hours=24)
    print(f"Deactivated: {count}")
```

## Тестирование

Расположение: `app/tests/test_property_repository.py`

14 тестов покрывают все основные операции:

```bash
pytest app/tests/test_property_repository.py -v
```

**Тестируемые функции:**
- ✅ Создание и получение объявлений
- ✅ Upsert операции
- ✅ Поиск с фильтрами
- ✅ История изменения цен
- ✅ Отслеживание просмотров
- ✅ Поисковые запросы
- ✅ Bulk операции
- ✅ Статистика

**Фикстуры в conftest.py:**
- `db_engine` - Async SQLite engine для тестов
- `db_session` - Async session с автоматическим rollback

## Производительность

### Оптимизации

1. **Индексы** - 9 индексов для быстрых запросов
2. **Connection pooling** - pool_size=10, max_overflow=20
3. **Bulk operations** - Пакетная вставка/обновление
4. **JSON fields** - Хранение сложных структур
5. **Async/await** - Неблокирующие операции

### Рекомендуемые настройки PostgreSQL

```ini
# postgresql.conf
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 6553kB
min_wal_size = 1GB
max_wal_size = 4GB
```

## Мониторинг

Добавьте логирование медленных запросов:

```python
# В настройках engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,  # Логирование SQL запросов
    pool_pre_ping=True
)
```

Метрики через Prometheus:
- Количество активных соединений
- Время выполнения запросов
- Количество объявлений по источникам

## Roadmap

- [ ] Полнотекстовый поиск по описаниям (PostgreSQL FTS)
- [ ] Геопространственные запросы (PostGIS)
- [ ] Партиционирование таблиц по датам
- [ ] Read replicas для масштабирования чтения
- [ ] Архивирование старых данных
