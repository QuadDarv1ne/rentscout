import time
from fastapi import APIRouter, Depends
from typing import Dict

from app.core.config import settings
from app.services.advanced_cache import advanced_cache_manager
from app.utils.ip_ratelimiter import ip_rate_limiter
from app.utils.logger import logger
from app.utils.metrics import metrics_collector, ACTIVE_REQUESTS

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check() -> Dict[str, str]:
    """Проверка состояния приложения."""
    return {"status": "healthy"}


@router.get("/health/detailed", tags=["health"])
async def detailed_health_check() -> Dict[str, object]:
    """Подробная проверка состояния приложения."""
    # Здесь можно добавить проверки подключений к базам данных, кэша и т.д.
    health_status = {"status": "healthy", "timestamp": time.time(), "app_name": settings.APP_NAME, "version": "1.0.0"}

    logger.info("Detailed health check performed")
    return health_status


@router.get("/stats", tags=["health"])
async def get_stats() -> Dict[str, object]:
    """Получение статистики приложения."""
    # Собираем статистику кеша
    cache_stats = await advanced_cache_manager.get_stats()
    active_requests = ACTIVE_REQUESTS._value.get()  # Gauge current value
    
    stats = {
        "uptime_seconds": metrics_collector.get_uptime(),
        "app_name": settings.APP_NAME,
        "version": "1.0.0",
        "cache": cache_stats,
        "active_requests": active_requests,
    }

    logger.info("Stats requested")
    return stats


@router.get("/cache/stats", tags=["health"])
async def get_cache_stats() -> Dict[str, object]:
    """Получение детальной статистики кеша."""
    cache_stats = await advanced_cache_manager.get_stats()
    logger.info(f"Cache stats: {cache_stats}")
    return cache_stats


@router.get("/ratelimit/stats", tags=["health"])
async def get_ratelimit_stats() -> Dict[str, object]:
    """Получение статистики rate limiting."""
    stats = ip_rate_limiter.get_stats()
    logger.info(f"Rate limit stats: {stats}")
    return stats
