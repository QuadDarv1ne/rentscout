# 🚀 Быстрый старт RentScout

Это руководство поможет вам запустить RentScout за 5 минут!

## Предварительные требования

- Docker и Docker Compose (рекомендуется)
- ИЛИ Python 3.9+ и PostgreSQL/Redis

## Вариант 1: Docker (Рекомендуется) ⚡

### Шаг 1: Клонируйте репозиторий

```bash
git clone https://github.com/QuadDarv1ne/rentscout.git
cd rentscout
```

### Шаг 2: Создайте .env файл

```bash
cp .env.example .env
```

Или создайте `.env` с минимальной конфигурацией:

```env
# Основные настройки
APP_NAME=RentScout
DEBUG=True
SECRET_KEY=your-secret-key-here-change-in-production

# База данных
DATABASE_URL=postgresql://rentscout:rentscout_password@postgres:5432/rentscout

# Redis
REDIS_URL=redis://redis:6379/0

# CORS (для фронтенда)
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

### Шаг 3: Запустите сервисы

```bash
docker-compose up -d
```

Это запустит:
- ✅ FastAPI приложение (порт 8000)
- ✅ PostgreSQL базу данных (порт 5432)
- ✅ Redis для кеширования (порт 6379)
- ✅ Celery worker для фоновых задач
- ✅ Prometheus метрики (порт 9090)
- ✅ Grafana дашборды (порт 3000)
- ✅ Nginx reverse proxy (порт 80)

### Шаг 4: Выполните миграции базы данных

```bash
docker-compose exec web alembic upgrade head
```

### Шаг 5: Откройте приложение

- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

## Вариант 2: Локальная установка 🔧

### Шаг 1: Клонируйте репозиторий

```bash
git clone https://github.com/QuadDarv1ne/rentscout.git
cd rentscout
```

### Шаг 2: Создайте виртуальное окружение

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### Шаг 3: Установите зависимости

```bash
pip install -r requirements.txt
```

### Шаг 4: Настройте базы данных

Установите и запустите PostgreSQL и Redis, затем создайте `.env`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/rentscout
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key
```

### Шаг 5: Выполните миграции

```bash
alembic upgrade head
```

### Шаг 6: Запустите приложение

```bash
uvicorn app.main:app --reload
```

Откройте http://localhost:8000/docs

## Первый запрос 🎯

### Поиск жилья в Москве

```bash
curl -X POST "http://localhost:8000/api/properties/search" \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Москва",
    "price_min": 30000,
    "price_max": 60000,
    "rooms_min": 2,
    "sources": ["avito", "cian"]
  }'
```

### Через браузер

Откройте http://localhost:8000/docs и используйте интерактивную документацию Swagger UI:

1. Разверните `POST /api/properties/search`
2. Нажмите "Try it out"
3. Введите параметры поиска
4. Нажмите "Execute"

## Основные API эндпоинты 📡

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Проверка состояния сервиса |
| `/api/properties/search` | POST | Поиск объявлений |
| `/api/properties/db` | GET | Список сохраненных объявлений |
| `/api/properties/db/{id}` | GET | Получить объявление по ID |
| `/api/bookmarks` | GET/POST | Управление закладками |
| `/api/alerts` | GET/POST | Управление оповещениями |
| `/api/ml/predict-price` | POST | ML предсказание цены |
| `/api/tasks/schedule-parsing` | POST | Запланировать парсинг |

## Примеры использования 💡

### Сохранить объявление в базу

```bash
curl -X POST "http://localhost:8000/api/properties/db" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "2-комнатная квартира",
    "price": 45000,
    "city": "Москва",
    "rooms": 2,
    "area": 55.5,
    "source": "avito",
    "url": "https://example.com/listing"
  }'
```

### Создать оповещение

```bash
curl -X POST "http://localhost:8000/api/alerts" \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Москва",
    "price_max": 50000,
    "rooms_min": 2,
    "email": "your@email.com"
  }'
```

### Получить предсказание цены

```bash
curl -X POST "http://localhost:8000/api/ml/predict-price" \
  -H "Content-Type: application/json" \
  -d '{
    "city": "Москва",
    "rooms": 2,
    "area": 55.5,
    "floor": 5,
    "total_floors": 10
  }'
```

## Тестирование 🧪

```bash
# Запустить все тесты
pytest

# С покрытием кода
pytest --cov=app --cov-report=html

# Конкретный тест
pytest app/tests/test_api.py -v
```

## Разработка 🛠️

### Установка pre-commit hooks

```bash
pip install pre-commit
pre-commit install
```

### Запуск линтеров

```bash
# Black форматирование
black app/

# isort сортировка импортов
isort app/

# Flake8 проверка стиля
flake8 app/

# MyPy проверка типов
mypy app/
```

### Создание новой миграции

```bash
alembic revision --autogenerate -m "описание изменений"
alembic upgrade head
```

## Остановка и очистка 🧹

```bash
# Остановить контейнеры
docker-compose down

# Остановить и удалить volumes
docker-compose down -v

# Очистить все (включая образы)
docker-compose down -v --rmi all
```

## Решение проблем 🔧

### Проблема: База данных не подключается

```bash
# Проверьте логи PostgreSQL
docker-compose logs postgres

# Пересоздайте контейнер
docker-compose down postgres
docker-compose up -d postgres
```

### Проблема: Redis не работает

```bash
# Проверьте логи Redis
docker-compose logs redis

# Перезапустите Redis
docker-compose restart redis
```

### Проблема: Порт уже занят

Измените порты в `docker-compose.yml` или остановите конфликтующий сервис:

```bash
# Windows
netstat -ano | findstr :8000

# Linux/macOS
lsof -i :8000
```

## Что дальше? 📚

- Прочитайте [полную документацию](README.md)
- Изучите [руководство разработчика](docs/DEV_GUIDE.md)
- Посмотрите [примеры API](docs/API.md)
- Настройте [оповещения и закладки](docs/NOTIFICATIONS_BOOKMARKS_GUIDE.md)
- Изучите [ML функции](docs/NEW_FEATURES.md)

## Поддержка 💬

- GitHub Issues: https://github.com/QuadDarv1ne/rentscout/issues
- Документация: [docs/](docs/)

## Лицензия 📄

MIT License - см. [LICENSE](LICENSE)

---

**Готово!** 🎉 RentScout запущен и готов к использованию!
