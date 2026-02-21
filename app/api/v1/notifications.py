"""
Notifications endpoints v1.
"""

from fastapi import APIRouter
from app.api.endpoints.notifications import router as original_router

router = APIRouter(prefix="/notifications", tags=["v1:notifications"])

for route in original_router.routes:
    router.routes.append(route)
