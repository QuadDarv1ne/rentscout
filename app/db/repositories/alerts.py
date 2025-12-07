"""
CRUD operations for PropertyAlert model.
"""
import logging
import time
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, update, delete, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.property import PropertyAlert
from app.utils.metrics import metrics_collector

logger = logging.getLogger(__name__)


# ==================== Property Alert CRUD ====================

async def create_alert(db: AsyncSession, alert_data: dict) -> PropertyAlert:
    """Create a new property alert."""
    start_time = time.time()
    
    try:
        db_alert = PropertyAlert(**alert_data)
        db.add(db_alert)
        await db.flush()
        await db.refresh(db_alert)
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("INSERT", "property_alerts", duration)
        
        logger.info(f"Created property alert: {db_alert.id} for {db_alert.email}")
        return db_alert
        
    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_db_query("INSERT", "property_alerts", duration, error=True)
        logger.error(f"Error creating property alert: {e}")
        raise


async def get_alert(db: AsyncSession, alert_id: int) -> Optional[PropertyAlert]:
    """Get a property alert by ID."""
    start_time = time.time()
    
    try:
        query = select(PropertyAlert).where(PropertyAlert.id == alert_id)
        result = await db.execute(query)
        alert = result.scalar_one_or_none()
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("SELECT", "property_alerts", duration)
        
        return alert
        
    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_db_query("SELECT", "property_alerts", duration, error=True)
        logger.error(f"Error getting property alert: {e}")
        raise


async def get_alerts_by_email(db: AsyncSession, email: str, active_only: bool = True) -> List[PropertyAlert]:
    """Get all property alerts for an email."""
    start_time = time.time()
    
    try:
        query = select(PropertyAlert).where(PropertyAlert.email == email)
        if active_only:
            query = query.where(PropertyAlert.is_active == True)
        query = query.order_by(desc(PropertyAlert.created_at))
        
        result = await db.execute(query)
        alerts = list(result.scalars().all())
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("SELECT", "property_alerts", duration)
        
        logger.info(f"Retrieved {len(alerts)} alerts for {email}")
        return alerts
        
    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_db_query("SELECT", "property_alerts", duration, error=True)
        logger.error(f"Error getting property alerts: {e}")
        raise


async def update_alert(db: AsyncSession, alert_id: int, update_data: dict) -> Optional[PropertyAlert]:
    """Update a property alert."""
    start_time = time.time()
    
    try:
        query = (
            update(PropertyAlert)
            .where(PropertyAlert.id == alert_id)
            .values(**update_data)
        )
        await db.execute(query)
        
        # Get the updated alert
        result = await db.execute(select(PropertyAlert).where(PropertyAlert.id == alert_id))
        updated_alert = result.scalar_one_or_none()
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("UPDATE", "property_alerts", duration)
        
        logger.info(f"Updated property alert: {alert_id}")
        return updated_alert
        
    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_db_query("UPDATE", "property_alerts", duration, error=True)
        logger.error(f"Error updating property alert: {e}")
        raise


async def deactivate_alert(db: AsyncSession, alert_id: int) -> bool:
    """Deactivate a property alert."""
    start_time = time.time()
    
    try:
        query = (
            update(PropertyAlert)
            .where(PropertyAlert.id == alert_id)
            .values(is_active=False)
        )
        result = await db.execute(query)
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("UPDATE", "property_alerts", duration)
        
        success = result.rowcount > 0
        if success:
            logger.info(f"Deactivated property alert: {alert_id}")
        return success
        
    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_db_query("UPDATE", "property_alerts", duration, error=True)
        logger.error(f"Error deactivating property alert: {e}")
        raise


async def delete_alert(db: AsyncSession, alert_id: int) -> bool:
    """Delete a property alert."""
    start_time = time.time()
    
    try:
        query = delete(PropertyAlert).where(PropertyAlert.id == alert_id)
        result = await db.execute(query)
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("DELETE", "property_alerts", duration)
        
        success = result.rowcount > 0
        if success:
            logger.info(f"Deleted property alert: {alert_id}")
        return success
        
    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_db_query("DELETE", "property_alerts", duration, error=True)
        logger.error(f"Error deleting property alert: {e}")
        raise


async def get_active_alerts(db: AsyncSession, limit: int = 1000) -> List[PropertyAlert]:
    """Get all active property alerts."""
    start_time = time.time()
    
    try:
        query = (
            select(PropertyAlert)
            .where(PropertyAlert.is_active == True)
            .order_by(PropertyAlert.created_at)
            .limit(limit)
        )
        
        result = await db.execute(query)
        alerts = list(result.scalars().all())
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("SELECT", "property_alerts", duration)
        
        logger.info(f"Retrieved {len(alerts)} active alerts")
        return alerts
        
    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_db_query("SELECT", "property_alerts", duration, error=True)
        logger.error(f"Error getting active property alerts: {e}")
        raise