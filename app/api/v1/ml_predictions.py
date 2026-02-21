"""
ML Predictions endpoints v1.
"""

from fastapi import APIRouter
from app.api.endpoints.ml_predictions import router as original_router

router = APIRouter(prefix="/ml", tags=["v1:ml-predictions"])

for route in original_router.routes:
    router.routes.append(route)
