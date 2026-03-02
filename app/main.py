import asyncio
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.router_registration import register_all_routers
from app.core.app_config import ROOT_API_RESPONSE, app_state, tags_metadata
from app.core.cache import cache_manager
from app.core.config import settings
from app.core.lifespan import lifespan
from app.core.monitoring import monitoring_system
from app.db.models.session import close_db, init_db
from app.middleware.compression import GZipMiddleware
from app.middleware.exception_handler import setup_exception_handlers
from app.middleware.security import (
    CORSMiddlewareConfig,
    HTTPSRedirectMiddleware,
    SecurityHeadersMiddleware,
)
from app.services.advanced_cache import advanced_cache_manager
from app.services.search import SearchService
from app.tasks.cache_maintenance import cache_maintenance, cache_warmer
from app.utils.advanced_metrics import SystemMetricsCollector
from app.utils.app_cache import app_cache
from app.utils.correlation_middleware import CorrelationIDMiddleware
from app.utils.http_pool import http_pool
from app.utils.ip_ratelimiter import RateLimitMiddleware
from app.utils.logger import logger
from app.utils.metrics import MetricsMiddleware
from app.utils import sentry as sentry_utils

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


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

# Добавление response compression для больших ответов
app.add_middleware(GZipMiddleware, minimum_size=1000, compression_level=6)

# Добавление middleware для HTTPS redirects и security headers
app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Добавление middleware для rate limiting по IP
app.add_middleware(RateLimitMiddleware)

# Добавление middleware для сбора метрик
app.add_middleware(MetricsMiddleware)

# Добавление CORS middleware с безопасной конфигурацией
cors_config = CORSMiddlewareConfig.get_cors_config()
app.add_middleware(
    CORSMiddleware,
    **cors_config
)

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Регистрируем все роутеры через централизованный модуль
register_all_routers(app)

# Регистрируем глобальные обработчики исключений
setup_exception_handlers(app)

# Подключаем GraphQL API
try:
    from app.api.graphql import graphql_app
    app.include_router(graphql_app, prefix="/graphql")
    logger.info("✅ GraphQL API enabled at /graphql")
except ImportError as e:
    logger.warning(f"GraphQL not available: {e}. Install with: pip install strawberry-graphql")

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


@app.get("/docs-custom", response_class=HTMLResponse, tags=["pages"], include_in_schema=False)
async def custom_docs(request: Request):
    """Кастомизированная Swagger UI документация"""
    return templates.TemplateResponse("swagger-custom.html", {"request": request})


@app.get("/api", tags=["root"])
async def root():
    """Корневой endpoint API с навигацией."""
    return ROOT_API_RESPONSE


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Favicon endpoint для предотвращения 404 в логах."""
    from fastapi.responses import Response
    # Возвращаем пустой favicon (можно заменить на настоящий)
    return Response(status_code=204)
