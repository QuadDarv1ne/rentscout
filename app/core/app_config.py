"""
Конфигурация и константы для FastAPI приложения.
"""

from typing import Any, Dict, List


tags_metadata: List[Dict[str, Any]] = [
    {
        "name": "authentication",
        "description": "Аутентификация и управление пользователями. Включает регистрацию, вход, обновление токенов, 2FA и управление профилем.",
    },
    {
        "name": "2FA",
        "description": "Двухфакторная аутентификация: настройка, включение/выключение, backup коды.",
    },
    {
        "name": "properties",
        "description": "Онлайн-поиск объявлений через парсеры с фильтрацией и кэшированием (Avito, Cian, Domofond, Yandex Realty и др.).",
    },
    {
        "name": "properties-db",
        "description": "CRUD и аналитика по объявлениям, сохранённым в PostgreSQL. Поиск, фильтрация, сравнение объектов.",
    },
    {
        "name": "properties-comparison",
        "description": "Сравнение объектов недвижимости по параметрам: цена, площадь, этаж, расположение.",
    },
    {
        "name": "price-alerts",
        "description": "Уведомления о снижении цены объектов. Создание, управление, получение активных уведомлений.",
    },
    {
        "name": "bookmarks",
        "description": "Избранные объекты недвижимости. Сохранение, управление коллекцией.",
    },
    {
        "name": "tasks",
        "description": "Фоновые задачи Celery для парсинга, расписаний и управления заданиями.",
    },
    {
        "name": "ml-predictions",
        "description": "ML предсказания цен, аналитика трендов и оптимизация ценообразования.",
    },
    {
        "name": "advanced-analytics",
        "description": "Расширенная аналитика: анализ объектов, прогноз цен, анализ спроса, сравнение локаций.",
    },
    {
        "name": "health",
        "description": "Проверки состояния сервиса, кеша и rate limit статистики.",
    },
    {
        "name": "quality-metrics",
        "description": "Метрики качества парсинга, анализ данных и отчёты о здоровье системы.",
    },
    {
        "name": "advanced-metrics",
        "description": "Расширенные метрики: health, summary, parsers, cache, API endpoints, system, prometheus.",
    },
    {
        "name": "parser-health",
        "description": "Мониторинг здоровья парсеров: статус, метрики, circuit breaker.",
    },
    {
        "name": "error-handling",
        "description": "Управление ошибками: логирование, анализ, circuit breaker, рекомендации.",
    },
    {
        "name": "batch-operations",
        "description": "Пакетные операции с объектами: update, delete, upsert, activate/deactivate.",
    },
    {
        "name": "cache-management",
        "description": "Управление кешем: очистка, инвалидация, мониторинг.",
    },
    {
        "name": "export",
        "description": "Экспорт данных в форматах JSON, CSV, JSONL.",
    },
    {
        "name": "websocket",
        "description": "WebSocket соединения для real-time уведомлений и мониторинга.",
    },
    {
        "name": "notifications",
        "description": "Система уведомлений: email, push, внутренние уведомления.",
    },
    {
        "name": "distributed-tracing",
        "description": "Распределённая трассировка запросов: мониторинг, анализ производительности.",
    },
    {
        "name": "auto-scaling",
        "description": "Автоматическое масштабирование ресурсов на основе нагрузки.",
    },
]

app_state: Dict[str, Any] = {
    "is_shutting_down": False,
    "active_requests": 0,
}

ROOT_API_RESPONSE = {
    "message": "Welcome to RentScout API",
    "version": "1.0.0",
    "status": "operational",
    "endpoints": {
        "documentation": "/docs",
        "alternative_docs": "/redoc",
        "health_check": "/api/health",
        "detailed_health": "/api/health/detailed",
        "search_properties": "/api/properties",
        "database_properties": "/api/db/properties",
        "tasks": "/api/tasks",
        "metrics": "/metrics",
    },
    "features": [
        "Multi-source property aggregation",
        "Advanced filtering (15+ parameters)",
        "Smart caching with Redis",
        "PostgreSQL full-text search",
        "Async background tasks with Celery",
        "Real-time metrics with Prometheus",
    ],
}
