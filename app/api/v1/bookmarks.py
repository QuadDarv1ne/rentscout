"""
Bookmarks endpoints v1.
"""

from fastapi import APIRouter
from app.api.endpoints.bookmarks import router as original_router

router = APIRouter(prefix="/bookmarks", tags=["v1:bookmarks"])

for route in original_router.routes:
    router.routes.append(route)
