"""
Properties endpoints v1.

Wrapper для существующих properties endpoint'ов версии v1.
"""

from fastapi import APIRouter

# Импортируем оригинальные endpoint'ы
from app.api.endpoints.properties import router as original_router

# Создаём роутер для v1
router = APIRouter(
    prefix="/properties",
    tags=["v1:properties"],
    responses={
        400: {"description": "Bad Request"},
        404: {"description": "Not Found"},
        500: {"description": "Internal Server Error"},
    },
)

# Копируем все route'ы из оригинального роутера
for route in original_router.routes:
    router.routes.append(route)


@router.get("/version")
async def properties_version():
    """Версия properties модуля."""
    return {"version": "v1", "module": "properties"}
