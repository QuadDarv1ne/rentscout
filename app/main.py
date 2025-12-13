from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from prometheus_fastapi_instrumentator import Instrumentator
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any
from pathlib import Path

from app.api.endpoints import health, properties, tasks, properties_db, advanced_search, notifications, bookmarks, ml_predictions, quality_metrics, advanced_metrics, batch_operations, error_handling, duplicates, cache_optimization, system_inspection, ml_cache_ttl, distributed_tracing, auto_scaling, advanced_analytics, performance_profiling, db_pool_monitoring
from app.core.config import settings
from app.services.advanced_cache import advanced_cache_manager
from app.services.search import SearchService
from app.utils.logger import logger
from app.utils.metrics import MetricsMiddleware
from app.utils.correlation_middleware import CorrelationIDMiddleware
from app.utils.ip_ratelimiter import RateLimitMiddleware
from app.utils.advanced_metrics import SystemMetricsCollector
from app.db.models.session import init_db, close_db
from app.utils.app_cache import app_cache
from app.utils.http_pool import http_pool
from app.tasks.cache_maintenance import cache_maintenance, cache_warmer

# Пути к статическим файлам и шаблонам
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Глобальное состояние приложения с правильной инициализацией
app_state: Dict[str, Any] = {
    "is_shutting_down": False,
    "active_requests": 0,
}

tags_metadata = [
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Управление жизненным циклом приложения с graceful shutdown."""
    # Startup
    logger.info(f"{settings.APP_NAME} application started")
    app_state["is_shutting_down"] = False
    app_state["active_requests"] = 0
    
    # Инициализация PostgreSQL (опционально, в production используем Alembic)
    if settings.DEBUG:
        try:
            await init_db()
            logger.info("✅ PostgreSQL database initialized")
        except Exception as e:
            # В dev режиме это нормально
            logger.debug(f"PostgreSQL unavailable: {type(e).__name__}")
            logger.info("ℹ️  PostgreSQL unavailable - running in-memory mode (use Docker: 'docker-compose -f docker-compose.dev.yml up postgres')")
    
    # Подключаемся к Redis
    await advanced_cache_manager.connect()
    
    # Инициализация нового app-level кеша
    await app_cache.initialize()
    logger.info("✅ Multi-level cache initialized")
    
    # Запуск автоматической очистки кеша
    await cache_maintenance.start()
    
    # Cache warming для популярных городов (асинхронно, не блокируем старт)
    if advanced_cache_manager.redis_client:
        search_service = SearchService()
        asyncio.create_task(
            advanced_cache_manager.warm_cache(
                search_service.search,
                cities=["Москва", "Санкт-Петербург"]  # Топ-2 города
            )
        )
        logger.info("🔥 Cache warming started for popular cities")
        
        # Запуск дополнительного cache warming
        asyncio.create_task(cache_warmer.warm_cache())
    
    yield
    
    # Shutdown
    logger.info(f"{settings.APP_NAME} starting graceful shutdown")
    app_state["is_shutting_down"] = True
    
    # Остановка cache maintenance
    await cache_maintenance.stop()
    
    # Логируем статистику кеша перед выключением
    cache_stats = await advanced_cache_manager.get_stats()
    logger.info(f"Final advanced cache statistics: {cache_stats}")
    
    app_cache_stats = app_cache.get_stats()
    logger.info(f"Final app cache statistics: {app_cache_stats}")
    
    # Отключаемся от Redis
    await advanced_cache_manager.disconnect()
    await app_cache.close()
    
    # Закрываем HTTP connection pool
    await http_pool.close_all()
    logger.info("✅ HTTP connection pool closed")
    
    # Закрываем PostgreSQL соединения
    await close_db()
    
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
    description="""
    ## 🏠 RentScout API
    
    **Высокопроизводительный сервис агрегации объявлений об аренде недвижимости**
    
    ### Основные возможности:
    - 🔍 Поиск объявлений с множественных площадок (Avito, Cian, и др.)
    - 🎯 Расширенная фильтрация (15+ параметров)
    - ⚡ Умное кеширование результатов
    - 📊 Встроенная аналитика и метрики
    - 🚀 Асинхронные фоновые задачи
    - 💾 Сохранение в PostgreSQL с полнотекстовым поиском
    
    ### Технологии:
    - FastAPI + Uvicorn
    - PostgreSQL + Redis
    - Celery + Flower
    - Prometheus + Grafana
    - Docker + Docker Compose
    
    ### Быстрый старт:
    1. Ознакомьтесь с эндпоинтами ниже
    2. Проверьте `/api/health` для статуса сервисов
    3. Используйте `/api/properties` для поиска
    4. Мониторьте `/metrics` для Prometheus
    
    > 💡 **Совет:** Используйте параметры `min_price`, `max_price`, `min_rooms`, `max_rooms` для точной фильтрации
    """,
    version="1.0.0",
    openapi_tags=tags_metadata,
    contact={
        "name": "RentScout Team",
        "url": "https://github.com/QuadDarv1ne/rentscout",
        "email": "support@rentscout.dev",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Подключение маршрутов
app.include_router(properties.router, prefix="/api", tags=["properties"])
app.include_router(advanced_search.router, prefix="/api", tags=["advanced-search"])
app.include_router(properties_db.router, prefix="/api/db", tags=["properties-db"])
# Алиас без дополнительного префикса (нужен для путей вида /properties/alerts в тестах)
app.include_router(properties_db.router, prefix="", tags=["properties-db-legacy"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(notifications.router, prefix="/api", tags=["notifications"])
app.include_router(bookmarks.router, prefix="/api", tags=["bookmarks"])
app.include_router(ml_predictions.router, prefix="/api", tags=["ml-predictions"])
app.include_router(quality_metrics.router, prefix="/api", tags=["quality-metrics"])
app.include_router(advanced_metrics.router, prefix="", tags=["metrics"])
app.include_router(batch_operations.router, prefix="", tags=["batch-processing"])
app.include_router(error_handling.router, prefix="", tags=["error-handling"])
app.include_router(duplicates.router, prefix="", tags=["duplicates"])
app.include_router(cache_optimization.router, prefix="", tags=["cache-optimization"])
app.include_router(system_inspection.router, prefix="", tags=["system-inspection"])

# v2.2.0 Routers - ML, Tracing, Auto-scaling, Analytics, Profiling
app.include_router(ml_cache_ttl.router, prefix="", tags=["ml-cache-ttl"])
app.include_router(distributed_tracing.router, prefix="", tags=["distributed-tracing"])
app.include_router(auto_scaling.router, prefix="", tags=["auto-scaling"])
app.include_router(advanced_analytics.router, prefix="", tags=["advanced-analytics"])
app.include_router(performance_profiling.router, prefix="", tags=["performance-profiling"])
app.include_router(db_pool_monitoring.router, prefix="", tags=["database-pool-monitoring"])


# Инициализация Prometheus инструментатора
Instrumentator().instrument(app).expose(app)

# Запуск сборщика системных метрик
SystemMetricsCollector.start_background_collection(interval=60)


# HTML страницы
@app.get("/", response_class=HTMLResponse, tags=["pages"])
async def home_page(request: Request):
    """Главная страница с информацией о сервисе"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/search", response_class=HTMLResponse, tags=["pages"])
async def search_page(request: Request):
    """Страница расширенного поиска"""
    return templates.TemplateResponse("search.html", {"request": request})


@app.get("/health-page", response_class=HTMLResponse, tags=["pages"])
async def health_page(request: Request):
    """Страница статуса системы"""
    return templates.TemplateResponse("health.html", {"request": request})


# API endpoint (корневой для API)
@app.get("/api", tags=["root"])
async def root():
    """
    # Корневой endpoint
    
    Предоставляет базовую информацию о API и навигацию по ключевым эндпоинтам.
    
    ## Возвращает:
    - **message**: Приветственное сообщение
    - **version**: Версия API
    - **status**: Статус сервиса
    - **endpoints**: Полезные ссылки для навигации
    
    ## Пример ответа:
    ```json
    {
        "message": "Welcome to RentScout API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "docs": "/docs",
            "health": "/api/health",
            "search": "/api/properties",
            "metrics": "/metrics"
        }
    }
    ```
    """
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
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


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Favicon endpoint для предотвращения 404 в логах."""
    from fastapi.responses import Response
    # Возвращаем пустой favicon (можно заменить на настоящий)
    return Response(status_code=204)
