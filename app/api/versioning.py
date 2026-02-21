"""
Модуль версионирования API.

Предоставляет структуру для поддержки нескольких версий API:
- /api/v1/... - текущая стабильная версия
- /api/v2/... - новая версия (в разработке)

Использование:
    from app.api.v1 import router as v1_router
    app.include_router(v1_router, prefix="/api/v1")
"""

from fastapi import APIRouter, FastAPI

from app.api.v1 import router as v1_router


# =============================================================================
# API Versioning Strategy
# =============================================================================
#
# Версионирование через URL path:
# - /api/v1/properties
# - /api/v1/auth/login
# - /api/v2/properties  (будущая версия)
#
# Преимущества:
# - Явная версия в URL
# - Простота тестирования
# - Обратная совместимость
#
# Стратегия депрекации:
# 1. Объявить о депрекации за 3 месяца
# 2. Добавить заголовок Deprecation в ответ
# 3. Вести логи использования старой версии
# 4. Отключить версию после окончания срока

# =============================================================================
# Version 1 (Current Stable)
# =============================================================================
# Все существующие endpoint'ы переезжают в v1

v1_router = APIRouter(prefix="/v1")

# Импортируем все роутеры из v1
from app.api.v1 import auth, properties, health, tasks, bookmarks, notifications, ml_predictions


def register_v1_routers(app: FastAPI) -> None:
    """
    Регистрирует все роутеры версии v1.
    
    Args:
        app: FastAPI приложение
    """
    app.include_router(auth.router, prefix="/api/v1", tags=["v1:authentication"])
    app.include_router(properties.router, prefix="/api/v1", tags=["v1:properties"])
    app.include_router(health.router, prefix="/api/v1", tags=["v1:health"])
    app.include_router(tasks.router, prefix="/api/v1", tags=["v1:tasks"])
    app.include_router(bookmarks.router, prefix="/api/v1", tags=["v1:bookmarks"])
    app.include_router(notifications.router, prefix="/api/v1", tags=["v1:notifications"])
    app.include_router(ml_predictions.router, prefix="/api/v1", tags=["v1:ml-predictions"])


# =============================================================================
# Version 2 (Future)
# =============================================================================
# Заготовки для будущей версии API

# v2_router = APIRouter(prefix="/v2")

# def register_v2_routers(app: FastAPI) -> None:
#     """Регистрирует роутеры версии v2."""
#     # app.include_router(v2_router, prefix="/api/v2")
#     pass


# =============================================================================
# Main Version Router
# =============================================================================

def register_versioned_routers(app: FastAPI, versions: list[str] = None) -> None:
    """
    Регистрирует все версионированные роутеры.
    
    Args:
        app: FastAPI приложение
        versions: Список версий для регистрации (по умолчанию ["v1"])
    """
    if versions is None:
        versions = ["v1"]
    
    if "v1" in versions:
        register_v1_routers(app)
    
    # if "v2" in versions:
    #     register_v2_routers(app)


# =============================================================================
# Deprecation Middleware
# =============================================================================

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class DeprecationMiddleware(BaseHTTPMiddleware):
    """
    Middleware для добавления заголовков депрекации.
    
    Добавляет заголовки:
    - Deprecation: true (если версия устарела)
    - Sunset: дата отключения
    - Link: ссылка на новую версию
    """
    
    DEPRECATED_VERSIONS = []  # Список устаревших версий
    SUNSET_DATES = {}  # Даты отключения версий
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Проверка версии в пути
        path = request.url.path
        for version in self.DEPRECATED_VERSIONS:
            if f"/api/{version}/" in path:
                response.headers["Deprecation"] = "true"
                
                if version in self.SUNSET_DATES:
                    response.headers["Sunset"] = self.SUNSET_DATES[version]
                
                # Ссылка на новую версию
                response.headers["Link"] = f'</api/v2/{path.split(f"/api/{version}/")[1]}>; rel="successor-version"'
        
        return response


# =============================================================================
# Version Info Endpoint
# =============================================================================

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

version_router = APIRouter(prefix="/version", tags=["version"])


class APIVersionInfo(BaseModel):
    """Информация о версии API."""
    version: str
    status: str  # current, deprecated, legacy
    deprecated: Optional[datetime] = None
    sunset: Optional[datetime] = None
    successor: Optional[str] = None


class APIVersionsResponse(BaseModel):
    """Ответ со списком версий API."""
    versions: list[APIVersionInfo]
    current_version: str


@version_router.get("/", response_model=APIVersionsResponse)
async def get_api_versions() -> dict:
    """
    Возвращает информацию о доступных версиях API.
    
    **Пример ответа:**
    ```json
    {
        "versions": [
            {
                "version": "v1",
                "status": "current",
                "deprecated": null,
                "sunset": null,
                "successor": null
            }
        ],
        "current_version": "v1"
    }
    ```
    """
    return {
        "versions": [
            {
                "version": "v1",
                "status": "current",
                "deprecated": None,
                "sunset": None,
                "successor": None,
            }
        ],
        "current_version": "v1",
    }


# =============================================================================
# Export
# =============================================================================

__all__ = [
    "v1_router",
    "register_v1_routers",
    "register_versioned_routers",
    "DeprecationMiddleware",
    "version_router",
    "APIVersionInfo",
    "APIVersionsResponse",
]
