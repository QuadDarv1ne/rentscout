"""
API endpoints for Database Connection Pool Monitoring
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.utils.db_pool_monitor import get_db_pool_health, db_pool_monitor

router = APIRouter()


@router.get("/api/db-pool/stats")
async def get_database_pool_stats() -> Dict[str, Any]:
    """
    Get database connection pool statistics and health metrics.
    
    Returns:
        Dictionary containing pool statistics, utilization metrics, and health status.
    """
    try:
        return get_db_pool_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving pool stats: {str(e)}")


@router.post("/api/db-pool/reset-stats")
async def reset_database_pool_stats() -> Dict[str, str]:
    """
    Reset database connection pool statistics.
    
    Returns:
        Success message.
    """
    try:
        db_pool_monitor.reset_stats()
        return {"status": "success", "message": "Database pool statistics reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting pool stats: {str(e)}")


@router.get("/api/db-pool/health")
async def get_database_pool_health() -> Dict[str, Any]:
    """
    Get database connection pool health status.
    
    Returns:
        Health status with recommendations if needed.
    """
    try:
        stats = get_db_pool_health()
        return {
            "status": "healthy" if stats["health_status"] == "healthy" else "degraded",
            "pool_utilization_percent": stats["current_pool_utilization"],
            "health_status": stats["health_status"],
            "recommendations": stats["recommendations"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving pool health: {str(e)}")