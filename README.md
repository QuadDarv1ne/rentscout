# 🏠 RentScout – Парсер арендной недвижимости

[![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python)](https://python.org)
[![Version](https://img.shields.io/badge/Version-v3.4.0-blue)](https://github.com/QuadDarv1ne/rentscout/releases)
[![License](https://img.shields.io/badge/License-MIT-red)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-✓-blue?logo=docker)](https://docker.com)

**RentScout** – это высокопроизводительный API для агрегации данных об аренде жилья с ведущих площадок.

Собирает актуальную информацию, фильтрует дубликаты и предоставляет удобный интерфейс для интеграции.

## 🌟 Особенности

### 🔍 Поиск и фильтрация
- **Поддержка 15+ фильтров**: цена (мин/макс), количество комнат (мин/макс), площадь (мин/макс), тип жилья и др.
- **Парсинг данных в реальном времени** с Avito, Cian, Domofond, Yandex Realty, DomClick и других площадок
- **Умное кеширование** результатов (Redis) — кеш на 5-10 минут
- **Сравнение объявлений** — сравнивайте 2-5 объектов по параметрам
- **Расширенная система оценки** — ранжирование объявлений по комплексным критериям

### 🗺️ Геолокация
- **Поиск ближайших объектов** — в радиусе 0.1-50 км от точки
- **Heatmap плотности** — визуализация плотности объектов по районам
- **Расчёт расстояний** — между точками с оценкой времени пешком/на велосипеде

### 🔐 Безопасность и аутентификация
- **Двухфакторная аутентификация (2FA)** — TOTP + backup коды
- **Rate limiting** — 5 попыток ввода 2FA в минуту, защита от brute-force
- **Валидация email** — проверка формата, домена, блокировка одноразовых email
- **Refresh token** — обновление пары токенов без повторного входа
- **Bcrypt шифрование** — backup коды хешируются (12 раундов)

### 📊 Аналитика и мониторинг
- **Персональные рекомендации** — получайте рекомендации на основе ваших предпочтений
- **Анализ трендов цен** — отслеживайте изменения цен на рынке недвижимости
- **Машинное обучение** — предсказание цен, анализ рынка и оптимизация ценообразования
- **Система оповещений** — уведомления о снижении цены объектов
- **Мониторинг метрик** через Prometheus + расширенные метрики производительности
- **Распределённая трассировка** — мониторинг запросов, анализ производительности

### ⚡ Производительность
- **Масштабируемая архитектура** на Docker
- **Circuit breaker** — защита от сбоев внешних сервисов
- **Retry logic** — автоматические повторные попытки с экспоненциальной задержкой
- **Оптимизированное подключение к БД** — массовые операции вставки
- **Автоматическое масштабирование** — на основе нагрузки

### 📦 Экспорт и интеграция
- **Экспорт данных** — выгрузка в форматах JSON, CSV, JSONL
- **WebSocket** — real-time уведомления и мониторинг
- **Пакетные операции** — update, delete, upsert, activate/deactivate
- **Автоматическая документация** Swagger/OpenAPI с 23 группами endpoints

## 🚀 Быстрый старт

> **⚡ Самый быстрый способ**: См. [QUICKSTART.md](QUICKSTART.md)

### Способ 1: Автоматический (рекомендуется)

```bash
git clone https://github.com/QuadDarv1ne/rentscout.git
cd rentscout
cp .env.example .env
docker-compose up -d
```

Откройте http://localhost:8000/docs

### Способ 2: Локальная установка

```bash
git clone https://github.com/QuadDarv1ne/rentscout.git
cd rentscout
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows
pip install -r requirements.txt
cp .env.example .env
# Настройте .env файл
alembic upgrade head
uvicorn app.main:app --reload
```

## 📚 Документация

### Основная документация
- [API Documentation](docs/API.md) — Полная документация API с примерами
- [Developer Guide](docs/DEVELOPER_GUIDE.md) — Руководство для разработчиков
- [Metrics Documentation](docs/METRICS.md) — Документация по метрикам и мониторингу
- [Notifications and Bookmarks Guide](docs/NOTIFICATIONS_BOOKMARKS_GUIDE.md) — Уведомления и закладки

### Руководства по функциям
- [2FA Implementation](docs/2FA_IMPLEMENTATION.md) — Двухфакторная аутентификация
- [2FA Examples](docs/2FA_EXAMPLES.md) — Примеры кода (Python, JS, cURL)
- [Геолокация API](app/api/endpoints/geolocation.py) — Поиск ближайших, heatmap, расстояния

## 🧪 Тестирование

```bash
# Запустить все тесты
pytest

# Запустить тесты с покрытием
pytest --cov=app

# Запустить конкретный тест
pytest app/tests/test_search_service.py

# Запустить тесты 2FA
pytest app/tests/test_2fa_unit.py -v

# Запустить тесты геолокации
pytest app/tests/test_geolocation.py -v
```

## 🐳 Docker

Проект поддерживает Docker и Docker Compose для легкого развертывания:

```bash
# Запустить все сервисы
docker-compose up -d

# Запустить только основное приложение
docker-compose up -d app

# Остановить все сервисы
docker-compose down

# Production режим
docker-compose -f docker-compose.prod.yml up -d
```

## 📈 Мониторинг

RentScout предоставляет метрики Prometheus по адресу `/metrics` для мониторинга производительности и состояния системы.

### Endpoints мониторинга
- `GET /metrics` — Prometheus метрики
- `GET /api/health` — Проверка состояния сервисов
- `GET /api/health/detailed` — Расширенная проверка
- `GET /api/health/parsers` — Статус парсеров
- `GET /metrics/summary` — Сводка метрик
- `GET /metrics/parsers` — Метрики парсеров
- `GET /metrics/cache` — Метрики кеша
- `GET /metrics/api-endpoints` — Статистика endpoints

## 🔑 API Endpoints

### Аутентификация
- `POST /api/auth/register` — Регистрация
- `POST /api/auth/login` — Вход (OAuth2)
- `POST /api/auth/login-with-2fa` — Вход с 2FA
- `POST /api/auth/refresh` — Обновление токена
- `POST /api/auth/2fa/setup` — Настройка 2FA
- `POST /api/auth/2fa/enable` — Включение 2FA
- `POST /api/auth/2fa/disable` — Отключение 2FA
- `GET /api/auth/2fa/status` — Статус 2FA

### Недвижимость
- `GET /api/properties` — Поиск объектов
- `GET /api/advanced-search` — Расширенный поиск
- `POST /api/properties/compare` — Сравнение объектов
- `GET /api/db/properties` — Объекты из БД

### Геолокация
- `POST /api/geo/nearby` — Поиск ближайших объектов
- `GET /api/geo/heatmap` — Heatmap плотности
- `POST /api/geo/distance` — Расчёт расстояния
- `GET /api/geo/cities` — Список городов

### Уведомления и закладки
- `GET /api/alerts` — Список уведомлений
- `POST /api/alerts` — Создать уведомление
- `GET /api/bookmarks` — Избранные объекты
- `POST /api/bookmarks` — Добавить в закладки

### Аналитика
- `GET /api/ml/predict` — Предсказание цены
- `GET /api/ml/trends` — Тренды цен
- `POST /api/analytics/property/analyze` — Анализ объекта
- `GET /api/analytics/summary` — Сводка аналитики

## 🤝 Вклад в проект

Мы приветствуем вклад в развитие проекта! См. [CONTRIBUTING.md](CONTRIBUTING.md) для получения дополнительной информации.

## 📄 Лицензия

Этот проект лицензирован по лицензии MIT-Style с ограничениями — см. файл [LICENSE](LICENSE) для получения подробной информации.

## 📊 Статистика проекта (v3.4.0)

| Метрика | Значение |
|---------|----------|
| **Версия** | v3.4.0 |
| **API Endpoints** | 235+ |
| **Парсеров** | 13 |
| **Тестов** | 155+ |
| **OpenAPI Tags** | 23 группы |
| **2FA Coverage** | 25+ unit-тестов |
| **Geo API** | 4 endpoints + 30 тестов |