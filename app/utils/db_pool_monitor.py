"""
Database Connection Pool Monitoring Utility

This module provides utilities for monitoring and optimizing
database connection pool performance.
"""

import logging
import time
from typing import Dict, Any
from sqlalchemy import event
from sqlalchemy.pool import Pool

from app.db.models.session import engine

logger = logging.getLogger(__name__)


class DatabasePoolMonitor:
    """Monitors database connection pool performance and statistics."""
    
    def __init__(self):
        self.checkout_count = 0
        self.checkin_count = 0
        self.connect_count = 0
        self.disconnect_count = 0
        self.checkout_times = []
        self.connection_errors = 0
        self._setup_event_listeners()
    
    def _setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for pool monitoring."""
        # Listen for connection checkout
        @event.listens_for(engine, "checkout")
        def checkout_listener(dbapi_connection, connection_record, connection_proxy):
            self.checkout_count += 1
            connection_record.info['checkout_time'] = time.time()
            logger.debug(f"Connection checked out from pool. Total checkouts: {self.checkout_count}")
        
        # Listen for connection checkin
        @event.listens_for(engine, "checkin")
        def checkin_listener(dbapi_connection, connection_record):
            self.checkin_count += 1
            checkout_time = connection_record.info.get('checkout_time')
            if checkout_time:
                duration = time.time() - checkout_time
                self.checkout_times.append(duration)
                logger.debug(f"Connection checked in to pool. Checkout duration: {duration:.3f}s")
        
        # Listen for connection creation
        @event.listens_for(engine, "connect")
        def connect_listener(dbapi_connection, connection_record):
            self.connect_count += 1
            logger.debug(f"New database connection created. Total connections: {self.connect_count}")
        
        # Listen for connection closure
        @event.listens_for(engine, "close")
        def close_listener(dbapi_connection, connection_record):
            self.disconnect_count += 1
            logger.debug(f"Database connection closed. Total disconnections: {self.disconnect_count}")
        
        # Listen for connection errors
        @event.listens_for(engine, "handle_error")
        def error_listener(exception_context):
            self.connection_errors += 1
            logger.warning(f"Database connection error occurred. Total errors: {self.connection_errors}")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get current pool statistics."""
        pool = engine.pool
        
        # Calculate average checkout time
        avg_checkout_time = 0.0
        if self.checkout_times:
            avg_checkout_time = sum(self.checkout_times) / len(self.checkout_times)
        
        return {
            "pool_size": pool.size() if hasattr(pool, 'size') else 0,
            "checked_out_connections": self.checkout_count - self.checkin_count,
            "total_checkouts": self.checkout_count,
            "total_checkins": self.checkin_count,
            "total_connections": self.connect_count,
            "total_disconnections": self.disconnect_count,
            "connection_errors": self.connection_errors,
            "average_checkout_time": round(avg_checkout_time, 3),
            "current_pool_utilization": round(
                (self.checkout_count - self.checkin_count) / pool.size() * 100 
                if pool.size() > 0 else 0, 2
            )
        }
    
    def reset_stats(self):
        """Reset all collected statistics."""
        self.checkout_count = 0
        self.checkin_count = 0
        self.connect_count = 0
        self.disconnect_count = 0
        self.checkout_times = []
        self.connection_errors = 0
        logger.info("Database pool statistics reset")


# Global instance
db_pool_monitor = DatabasePoolMonitor()


def get_db_pool_health() -> Dict[str, Any]:
    """
    Get database pool health status.
    
    Returns:
        Dictionary with pool health metrics
    """
    stats = db_pool_monitor.get_pool_stats()
    
    # Determine health status
    utilization = stats["current_pool_utilization"]
    if utilization > 90:
        health_status = "critical"
    elif utilization > 75:
        health_status = "warning"
    else:
        health_status = "healthy"
    
    # Add health assessment
    stats["health_status"] = health_status
    stats["recommendations"] = []
    
    # Add recommendations based on metrics
    if utilization > 80:
        stats["recommendations"].append(
            "Consider increasing pool size or optimizing query performance"
        )
    
    if stats["connection_errors"] > 10:
        stats["recommendations"].append(
            "Investigate connection errors - check network stability and database availability"
        )
    
    if stats["average_checkout_time"] > 5.0:
        stats["recommendations"].append(
            "High checkout times - consider optimizing queries or adding indexes"
        )
    
    return stats


# API endpoint for monitoring
async def db_pool_monitoring_endpoint():
    """
    FastAPI endpoint for database pool monitoring.
    
    Returns:
        JSON response with pool statistics and health metrics
    """
    return get_db_pool_health()