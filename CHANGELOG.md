# Changelog

Все значительные изменения в этом проекте будут документироваться в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
и этот проект следует [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions CI/CD pipeline с автоматическим тестированием
- Pre-commit hooks для автоматической проверки кода
- Security scanning с Bandit и Safety
- Dependabot для автоматического обновления зависимостей
- Улучшенная Docker конфигурация с multi-stage build
- Nginx reverse proxy с rate limiting
- Grafana для визуализации метрик
- QUICKSTART.md для быстрого старта
- .env.example с подробной конфигурацией
- CONTRIBUTING_DETAILED.md с руководством для контрибьюторов
- SECURITY.md с политикой безопасности
- .dockerignore для оптимизации сборки
- .yamllint.yml для проверки YAML файлов

### Changed
- Обновлен docker-compose.yml с полным стеком (PostgreSQL, Redis, Celery, Prometheus, Grafana, Nginx)
- Улучшен Dockerfile с безопасностью и оптимизацией
- Оптимизирована структура проекта

### Security
- Добавлен непривилегированный пользователь в Docker
- Настроены security headers в Nginx
- Включен Bandit для проверки безопасности кода

## [1.5.0] - 2025-12-08

### Added
- ML предсказания цен недвижимости
- Анализ трендов цен
- Система оповещений о новых объявлениях
- Закладки для сохранения понравившихся объявлений
- Advanced кеширование с Redis
- Улучшенная обработка ошибок с circuit breaker
- Метрики производительности с Prometheus
- IP-based rate limiting
- Correlation ID для отслеживания запросов

### Changed
- Оптимизирована работа с базой данных
- Улучшена производительность парсеров
- Обновлена документация

### Fixed
- Исправлены критические ошибки в парсерах
- Улучшена стабильность системы

## [1.4.0] - 2025-12-07

### Added
- Расширенная фильтрация объявлений
- Поддержка Elasticsearch для поиска
- Query analyzer для оптимизации запросов
- Асинхронный экспорт данных
- Улучшенное логирование

### Changed
- Рефакторинг структуры базы данных
- Оптимизация SQL запросов

## [1.3.0] - 2025-12-06

### Added
- Поддержка PostgreSQL
- Alembic для миграций базы данных
- CRUD операции для объявлений
- Сравнение объявлений
- Персональные рекомендации

### Changed
- Переход с SQLite на PostgreSQL
- Улучшена архитектура приложения

## [1.2.0] - 2025-12-05

### Added
- Парсер Yandex Realty
- Парсер Domofond
- Кеширование результатов поиска
- Rate limiting для защиты от перегрузки

### Changed
- Оптимизирован парсинг данных
- Улучшена обработка ошибок

## [1.1.0] - 2025-12-04

### Added
- Парсер Cian
- Фильтрация по площади
- Фильтрация по типу жилья
- Swagger UI документация

### Changed
- Улучшена производительность API
- Обновлена документация

### Fixed
- Исправлены ошибки в парсере Avito

## [1.0.0] - 2025-12-03

### Added
- Первый релиз RentScout
- Базовый парсер Avito
- REST API с FastAPI
- Фильтрация по городу, цене, комнатам
- Базовое кеширование
- Docker поддержка
- Документация API

### Changed
- Начальная версия

[Unreleased]: https://github.com/QuadDarv1ne/rentscout/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/QuadDarv1ne/rentscout/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/QuadDarv1ne/rentscout/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/QuadDarv1ne/rentscout/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/QuadDarv1ne/rentscout/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/QuadDarv1ne/rentscout/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/QuadDarv1ne/rentscout/releases/tag/v1.0.0
