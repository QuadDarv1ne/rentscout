"""
Модуль регистрации всех API роутеров.

Выносит логику регистрации роутеров из main.py для улучшения читаемости.
"""

from fastapi import FastAPI

from app.api.endpoints import (
    auth,
    properties,
    advanced_search,
    properties_db,
    health,
    tasks,
    notifications,
    bookmarks,
    ml_predictions,
    quality_metrics,
    advanced_metrics,
    batch_operations,
    error_handling,
    cache_optimization,
    system_inspection,
    ml_cache_ttl,
    distributed_tracing,
    auto_scaling,
    advanced_analytics,
    performance_profiling,
    db_pool_monitoring,
)


def register_all_routers(app: FastAPI) -> None:
    """
    Регистрирует все API роутеры в приложении.

    Args:
        app: Экземпляр FastAPI приложения
    """
    # Authentication & Users
    app.include_router(auth.router, prefix="/api", tags=["authentication"])

    # Properties Search
    app.include_router(properties.router, prefix="/api", tags=["properties"])
    app.include_router(advanced_search.router, prefix="/api", tags=["advanced-search"])

    # Database Properties
    app.include_router(properties_db.router, prefix="/api/db", tags=["properties-db"])

    # Health & Monitoring
    app.include_router(health.router, prefix="/api", tags=["health"])

    # Background Tasks
    app.include_router(tasks.router, prefix="/api", tags=["tasks"])

    # Notifications & Bookmarks
    app.include_router(notifications.router, prefix="/api", tags=["notifications"])
    app.include_router(bookmarks.router, prefix="/api", tags=["bookmarks"])

    # ML & Analytics
    app.include_router(ml_predictions.router, prefix="/api", tags=["ml-predictions"])
    app.include_router(quality_metrics.router, prefix="/api", tags=["quality-metrics"])

    # Metrics & Monitoring (без префикса для Prometheus совместимости)
    app.include_router(advanced_metrics.router, prefix="", tags=["metrics"])

    # Batch Operations
    app.include_router(batch_operations.router, prefix="", tags=["batch-processing"])

    # Error Handling
    app.include_router(error_handling.router, prefix="", tags=["error-handling"])

    # Cache Optimization
    app.include_router(cache_optimization.router, prefix="", tags=["cache-optimization"])

    # System Inspection
    app.include_router(system_inspection.router, prefix="", tags=["system-inspection"])

    # ML Cache TTL
    app.include_router(ml_cache_ttl.router, prefix="", tags=["ml-cache-ttl"])

    # Distributed Tracing
    app.include_router(distributed_tracing.router, prefix="", tags=["distributed-tracing"])

    # Auto Scaling
    app.include_router(auto_scaling.router, prefix="", tags=["auto-scaling"])

    # Advanced Analytics
    app.include_router(advanced_analytics.router, prefix="", tags=["advanced-analytics"])

    # Performance Profiling
    app.include_router(performance_profiling.router, prefix="", tags=["performance-profiling"])

    # Database Pool Monitoring
    app.include_router(db_pool_monitoring.router, prefix="", tags=["database-pool-monitoring"])


def get_router_summary() -> dict[str, list[str]]:
    """
    Возвращает краткую сводку по зарегистрированным роутерам.

    Returns:
        Словарь с группами роутеров и их префиксами
    """
    return {
        "authentication": ["/api/auth"],
        "properties": ["/api/properties", "/api/advanced-search"],
        "database": ["/api/db/properties"],
        "health": ["/api/health"],
        "tasks": ["/api/tasks"],
        "notifications": ["/api/notifications"],
        "bookmarks": ["/api/bookmarks"],
        "ml": ["/api/ml"],
        "metrics": ["/metrics"],
        "batch": ["/batch"],
        "errors": ["/errors"],
        "cache": ["/cache"],
        "system": ["/system"],
        "tracing": ["/tracing"],
        "scaling": ["/scaling"],
        "analytics": ["/analytics"],
        "profiling": ["/profiling"],
        "db-pool": ["/db-pool"],
    }


__all__ = [
    "register_all_routers",
    "get_router_summary",
]
