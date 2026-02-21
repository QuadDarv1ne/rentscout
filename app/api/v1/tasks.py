"""
Tasks endpoints v1.
"""

from fastapi import APIRouter
from app.api.endpoints.tasks import router as original_router

router = APIRouter(prefix="/tasks", tags=["v1:tasks"])

for route in original_router.routes:
    router.routes.append(route)
