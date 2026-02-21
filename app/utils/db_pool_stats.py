"""Утилиты для мониторинга connection pool."""

from typing import Dict, Any
from app.db.models.session import engine
from app.utils.logger import logger


def get_pool_stats() -> Dict[str, Any]:
    """Получить статистику connection pool."""
    pool = engine.pool
    
    stats = {
        "size": pool.size(),
        "checked_in": 0,
        "checked_out": 0,
        "overflow": 0,
        "total_connections": 0,
    }
    
    try:
        if hasattr(pool, 'checkedin'):
            stats["checked_in"] = pool.checkedin()
        if hasattr(pool, 'checkedout'):
            stats["checked_out"] = pool.checkedout()
        if hasattr(pool, 'overflow'):
            stats["overflow"] = pool.overflow()
        
        stats["total_connections"] = stats["checked_in"] + stats["checked_out"]
        
        # Вычисляем утилизацию пула
        if stats["size"] > 0:
            stats["utilization_percent"] = (stats["checked_out"] / stats["size"]) * 100
        else:
            stats["utilization_percent"] = 0
        
    except Exception as e:
        logger.warning(f"Failed to get pool stats: {e}")
    
    return stats


def log_pool_stats():
    """Логировать статистику пула."""
    stats = get_pool_stats()
    logger.info(
        f"DB Pool: {stats['checked_out']}/{stats['size']} in use, "
        f"{stats['checked_in']} available, "
        f"{stats['overflow']} overflow, "
        f"{stats['utilization_percent']:.1f}% utilization"
    )
