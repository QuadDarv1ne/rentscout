"""
API Version 1 (v1) - Current Stable Version

Все endpoint'ы версии v1.
"""

from app.api.v1.auth import router as auth
from app.api.v1.properties import router as properties
from app.api.v1.health import router as health
from app.api.v1.tasks import router as tasks
from app.api.v1.bookmarks import router as bookmarks
from app.api.v1.notifications import router as notifications
from app.api.v1.ml_predictions import router as ml_predictions

__all__ = [
    "auth",
    "properties",
    "health",
    "tasks",
    "bookmarks",
    "notifications",
    "ml_predictions",
]
