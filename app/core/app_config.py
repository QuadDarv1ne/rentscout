"""
Конфигурация и константы для FastAPI приложения.
"""

from typing import Any, Dict, List


tags_metadata: List[Dict[str, Any]] = [
    {
        "name": "authentication",
        "description": "Аутентификация и управление пользователями. Включает регистрацию, вход, обновление токенов и управление профилем.",
    },
    {
        "name": "properties",
        "description": "Онлайн-поиск объявлений через парсеры с фильтрацией и кэшированием.",
    },
    {
        "name": "properties-db",
        "description": "CRUD и аналитика по объявлениям, сохранённым в PostgreSQL.",
    },
    {
        "name": "tasks",
        "description": "Фоновые задачи Celery для парсинга, расписаний и управления заданиями.",
    },
    {
        "name": "health",
        "description": "Проверки состояния сервиса, кеша и rate limit статистики.",
    },
    {
        "name": "ml-predictions",
        "description": "ML предсказания цен, аналитика трендов и оптимизация ценообразования.",
    },
    {
        "name": "quality-metrics",
        "description": "Метрики качества парсинга, анализ данных и отчёты о здоровье системы.",
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
