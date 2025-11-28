import time
from fastapi import APIRouter, Depends
from typing import Dict

from app.core.config import settings
from app.utils.logger import logger

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
    # Здесь можно добавить сбор статистики по использованию API
    stats = {"uptime": time.time(), "app_name": settings.APP_NAME, "version": "1.0.0"}

    logger.info("Stats requested")
    return stats
