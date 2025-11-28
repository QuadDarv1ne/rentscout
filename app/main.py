from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.endpoints import health, properties
from app.core.config import settings
from app.utils.logger import logger
from app.utils.metrics import MetricsMiddleware

# Создание экземпляра FastAPI приложения
app = FastAPI(
    title=settings.APP_NAME, description="API для агрегации данных об аренде жилья с ведущих площадок", version="1.0.0"
)

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

# Инициализация Prometheus инструментатора
Instrumentator().instrument(app).expose(app)


@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения."""
    logger.info(f"{settings.APP_NAME} application started")
    # Здесь можно добавить инициализацию подключений к базам данных, кэша и т.д.


@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке приложения."""
    logger.info(f"{settings.APP_NAME} application shutting down")
    # Здесь можно добавить закрытие подключений и освобождение ресурсов


@app.get("/", tags=["root"])
async def root():
    """Корневой endpoint."""
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
