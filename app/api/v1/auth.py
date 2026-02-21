"""
Auth endpoints v1.

Wrapper для существующих auth endpoint'ов версии v1.
"""

from fastapi import APIRouter

# Импортируем оригинальные endpoint'ы
from app.api.endpoints.auth import router as original_router

# Создаём роутер для v1
router = APIRouter(
    prefix="/auth",
    tags=["v1:authentication"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        429: {"description": "Too Many Requests"},
    },
)

# Копируем все route'ы из оригинального роутера
for route in original_router.routes:
    router.routes.append(route)


@router.get("/version")
async def auth_version():
    """Версия auth модуля."""
    return {"version": "v1", "module": "auth"}
