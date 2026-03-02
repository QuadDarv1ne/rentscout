"""
Lifespan events для FastAPI приложения.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.core.app_config import app_state
from app.core.cache import cache_manager
from app.core.config import settings
from app.core.monitoring import monitoring_system
from app.db.models.session import close_db, init_db
from app.services.advanced_cache import advanced_cache_manager
from app.services.search import SearchService
from app.tasks.cache_maintenance import cache_maintenance, cache_warmer
from app.utils.app_cache import app_cache
from app.utils.http_pool import http_pool
from app.utils import sentry as sentry_utils
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Управление жизненным циклом приложения с graceful shutdown."""
    # Startup
    sentry_utils.init_sentry()

    logger.info(f"{settings.APP_NAME} application startup initiated")
    app_state["is_shutting_down"] = False
    app_state["active_requests"] = 0

    # Инициализация PostgreSQL
    if settings.DEBUG:
        try:
            await init_db()
            logger.info("✅ PostgreSQL database initialized")
        except Exception as e:
            logger.warning(f"PostgreSQL unavailable: {e}")
            logger.info("ℹ️  Running in-memory mode")

    # Подключаемся к Redis
    try:
        await advanced_cache_manager.connect()
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")

    # Инициализация кешей
    try:
        await app_cache.initialize()
        logger.info("✅ Multi-level cache initialized")
    except Exception as e:
        logger.warning(f"App cache initialization failed: {e}")

    try:
        await cache_manager.initialize()
        logger.info("✅ Advanced cache manager initialized")
    except Exception as e:
        logger.warning(f"Cache manager initialization failed: {e}")

    # Запуск monitoring system
    try:
        await monitoring_system.start(check_interval_seconds=60)
        logger.info("✅ Monitoring system started")
    except Exception as e:
        logger.warning(f"Monitoring system startup failed: {e}")

    # Запуск cache maintenance
    try:
        await cache_maintenance.start()
    except Exception as e:
        logger.warning(f"Cache maintenance startup failed: {e}")

    # Cache warming
    if hasattr(advanced_cache_manager, 'redis_client') and advanced_cache_manager.redis_client:
        try:
            search_service = SearchService()
            asyncio.create_task(
                advanced_cache_manager.warm_cache(
                    search_service.search,
                    cities=["Москва", "Санкт-Петербург"]
                )
            )
            logger.info("🔥 Cache warming started for popular cities")
            asyncio.create_task(cache_warmer.warm_cache())
        except Exception as e:
            logger.warning(f"Cache warming failed: {e}")

    logger.info(f"{settings.APP_NAME} application startup complete")
    yield

    # Shutdown
    logger.info(f"{settings.APP_NAME} starting graceful shutdown")
    app_state["is_shutting_down"] = True

    # Остановка компонентов
    await monitoring_system.stop()
    await cache_maintenance.stop()

    # Логирование статистики
    try:
        cache_stats = await advanced_cache_manager.get_stats()
        logger.info(f"Final advanced cache statistics: {cache_stats}")
    except Exception:
        pass

    try:
        app_cache_stats = app_cache.get_stats()
        logger.info(f"Final app cache statistics: {app_cache_stats}")
    except Exception:
        pass

    # Отключение от Redis
    try:
        await advanced_cache_manager.disconnect()
    except Exception:
        pass

    try:
        await app_cache.close()
    except Exception:
        pass

    try:
        await cache_manager.shutdown()
    except Exception:
        pass

    # Закрытие HTTP pool
    try:
        await http_pool.close_all()
        logger.info("✅ HTTP connection pool closed")
    except Exception:
        pass

    # Закрытие PostgreSQL
    try:
        await close_db()
    except Exception:
        pass

    # Graceful shutdown для активных запросов
    await _wait_for_active_requests()

    logger.info(f"{settings.APP_NAME} application shut down successfully")


async def _wait_for_active_requests() -> None:
    """Ожидание завершения активных запросов."""
    max_wait_time = 30
    start_time = asyncio.get_event_loop().time()

    while app_state["active_requests"] > 0:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > max_wait_time:
            logger.warning(
                f"Graceful shutdown timeout reached. "
                f"{app_state['active_requests']} requests still active."
            )
            break

        logger.info(
            f"Waiting for {app_state['active_requests']} active requests... "
            f"({elapsed:.1f}s/{max_wait_time}s)"
        )
        await asyncio.sleep(1)
