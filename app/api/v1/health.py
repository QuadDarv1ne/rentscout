"""
Health endpoints v1.
"""

from fastapi import APIRouter
from app.api.endpoints.health import router as original_router

router = APIRouter(prefix="/health", tags=["v1:health"])

for route in original_router.routes:
    router.routes.append(route)
