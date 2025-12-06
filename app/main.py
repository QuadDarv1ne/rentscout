from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any

from app.api.endpoints import health, properties, tasks
from app.core.config import settings
from app.services.advanced_cache import advanced_cache_manager
from app.services.search import SearchService
from app.utils.logger import logger
from app.utils.metrics import MetricsMiddleware
from app.utils.correlation_middleware import CorrelationIDMiddleware
from app.utils.ip_ratelimiter import RateLimitMiddleware

# Глобальное состояние приложения с правильной инициализацией
app_state: Dict[str, Any] = {
    "is_shutting_down": False,
    "active_requests": 0,
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Управление жизненным циклом приложения с graceful shutdown."""
    # Startup
    logger.info(f"{settings.APP_NAME} application started")
    app_state["is_shutting_down"] = False
    app_state["active_requests"] = 0
    
    # Подключаемся к Redis
    await advanced_cache_manager.connect()
    
    # Cache warming для популярных городов (асинхронно, не блокируем старт)
    if advanced_cache_manager.redis_client:
        search_service = SearchService()
        asyncio.create_task(
            advanced_cache_manager.warm_cache(
                search_service.search,
                cities=["Москва", "Санкт-Петербург"]  # Топ-2 города
            )
        )
        logger.info("Cache warming task started in background")
    
    yield
    
    # Shutdown
    logger.info(f"{settings.APP_NAME} starting graceful shutdown")
    app_state["is_shutting_down"] = True
    
    # Логируем статистику кеша перед выключением
    cache_stats = await advanced_cache_manager.get_stats()
    logger.info(f"Final cache statistics: {cache_stats}")
    
    # Отключаемся от Redis
    await advanced_cache_manager.disconnect()
    
    # Ждем завершения активных запросов (максимум 30 секунд)
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
            f"Waiting for {app_state['active_requests']} active requests to complete... "
            f"({elapsed:.1f}s/{max_wait_time}s)"
        )
        await asyncio.sleep(1)
    
    logger.info(f"{settings.APP_NAME} application shut down successfully")


# Создание экземпляра FastAPI приложения с lifespan
app = FastAPI(
    title=settings.APP_NAME,
    description="API для агрегации данных об аренде жилья с ведущих площадок",
    version="1.0.0",
    lifespan=lifespan,
)



# Добавление middleware для correlation IDs (добавляем первым)
app.add_middleware(CorrelationIDMiddleware)

# Добавление middleware для rate limiting по IP
app.add_middleware(RateLimitMiddleware)

# Добавление middleware для сбора метрик
app.add_middleware(MetricsMiddleware)

# Добавление CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В production следует указать конкретные origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение маршрутов
app.include_router(properties.router, prefix="/api", tags=["properties"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])

# Инициализация Prometheus инструментатора
Instrumentator().instrument(app).expose(app)


@app.get("/", tags=["root"])
async def root():
    """Корневой endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
