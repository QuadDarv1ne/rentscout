"""Утилиты для работы с датой и временем."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Получить текущее UTC время (совместимо с Python 3.11+)."""
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    """Получить текущий UTC timestamp в ISO формате."""
    return utcnow().isoformat()
