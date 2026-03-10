"""
Optimized CRUD operations with N+1 query prevention.

Использует selectinload/joinedload для eager loading связанных данных.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import select, update, delete, and_, or_, func, desc
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.property import Property, PropertyPriceHistory, PropertyView, SearchQuery
from app.models.schemas import PropertyCreate
from app.utils.metrics import metrics_collector

logger = logging.getLogger(__name__)


# ==================== Optimized Property Queries ====================

async def get_property_with_history(
    db: AsyncSession,
    property_id: int
) -> Optional[Tuple[Property, List[PropertyPriceHistory]]]:
    """
    Get property with price history in single query (prevents N+1).

    Uses selectinload for eager loading of related data.
    """
    start_time = time.time()

    query = (
        select(Property)
        .options(selectinload(Property.price_history))  # Eager load history
        .where(Property.id == property_id)
    )

    result = await db.execute(query)
    property_obj = result.scalar_one_or_none()

    if not property_obj:
        return None

    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT_WITH_HISTORY", "properties", duration)

    return property_obj, property_obj.price_history


async def get_properties_with_filters_optimized(
    db: AsyncSession,
    city: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rooms: Optional[int] = None,
    max_rooms: Optional[int] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    source: Optional[str] = None,
    district: Optional[str] = None,
    is_active: bool = True,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 100,
    offset: int = 0,
    options=None  # Additional loader options
) -> List[Property]:
    """
    Optimized property search with eager loading.

    Args:
        db: Database session
        city: Filter by city
        min_price: Minimum price
        max_price: Maximum price
        min_rooms: Minimum rooms
        max_rooms: Maximum rooms
        min_area: Minimum area
        max_area: Maximum area
        source: Filter by source
        district: Filter by district
        is_active: Filter by active status
        sort_by: Sort field
        sort_order: Sort order (asc/desc)
        limit: Limit results
        offset: Offset results
        options: Additional SQLAlchemy loader options

    Returns:
        List of Property objects
    """
    start_time = time.time()

    # Base query with eager loading
    query = select(Property).options(
        selectinload(Property.price_history)  # Prevent N+1 for history
    )

    # Add custom options if provided
    if options:
        query = query.options(*options)

    # Build filters
    filters = [Property.is_active == is_active] if is_active is not None else []

    if city:
        filters.append(Property.city == city)
    if source:
        filters.append(Property.source == source)
    if district:
        filters.append(Property.district == district)
    if min_price is not None:
        filters.append(Property.price >= min_price)
    if max_price is not None:
        filters.append(Property.price <= max_price)
    if min_rooms is not None:
        filters.append(Property.rooms >= min_rooms)
    if max_rooms is not None:
        filters.append(Property.rooms <= max_rooms)
    if min_area is not None:
        filters.append(Property.area >= min_area)
    if max_area is not None:
        filters.append(Property.area <= max_area)

    query = query.where(and_(*filters))

    # Apply sorting
    if sort_order == "desc":
        if sort_by == "price":
            query = query.order_by(desc(Property.price))
        elif sort_by == "area":
            query = query.order_by(desc(Property.area))
        elif sort_by == "rooms":
            query = query.order_by(desc(Property.rooms))
        elif sort_by == "first_seen":
            query = query.order_by(desc(Property.first_seen))
        elif sort_by == "last_seen":
            query = query.order_by(desc(Property.last_seen))
        else:  # default to created_at
            query = query.order_by(desc(Property.created_at))
    else:  # asc
        if sort_by == "price":
            query = query.order_by(Property.price)
        elif sort_by == "area":
            query = query.order_by(Property.area)
        elif sort_by == "rooms":
            query = query.order_by(Property.rooms)
        elif sort_by == "first_seen":
            query = query.order_by(Property.first_seen)
        elif sort_by == "last_seen":
            query = query.order_by(Property.last_seen)
        else:  # default to created_at
            query = query.order_by(Property.created_at)

    # Apply pagination
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    properties = list(result.scalars().all())

    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT_OPTIMIZED", "properties", duration)

    logger.debug(f"Optimized query returned {len(properties)} properties in {duration:.3f}s")
    return properties


async def get_property_with_views(
    db: AsyncSession,
    property_id: int,
    days: int = 30
) -> Optional[Tuple[Property, int]]:
    """
    Get property with view count in optimized query.

    Uses subquery for count to avoid N+1.
    """
    start_time = time.time()

    threshold = datetime.utcnow() - timedelta(days=days)

    # Subquery for view count
    view_count_subq = (
        select(func.count(PropertyView.id))
        .where(
            and_(
                PropertyView.property_id == Property.id,
                PropertyView.viewed_at >= threshold
            )
        )
        .correlate(Property)
        .scalar_subquery()
    )

    query = (
        select(Property, view_count_subq.label("view_count"))
        .where(Property.id == property_id)
    )

    result = await db.execute(query)
    row = result.first()

    if not row:
        return None

    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT_WITH_VIEWS", "properties", duration)

    return row[0], row[1]


async def get_properties_batch(
    db: AsyncSession,
    property_ids: List[int],
    load_history: bool = False,
    load_views: bool = False
) -> List[Property]:
    """
    Get multiple properties in single query with optional eager loading.

    Prevents N+1 when fetching multiple properties.

    Args:
        db: Database session
        property_ids: List of property IDs
        load_history: If True, eager load price history
        load_views: If True, eager load view counts

    Returns:
        List of Property objects
    """
    start_time = time.time()

    if not property_ids:
        return []

    # Build options
    options = []
    if load_history:
        options.append(selectinload(Property.price_history))

    # Base query
    query = select(Property).where(Property.id.in_(property_ids))

    # Add options
    if options:
        query = query.options(*options)

    result = await db.execute(query)
    properties = list(result.scalars().all())

    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT_BATCH", "properties", duration)

    logger.debug(f"Batch loaded {len(properties)} properties in {duration:.3f}s")
    return properties


async def get_properties_enriched(
    db: AsyncSession,
    city: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Get properties with enriched data in single query.

    Returns dict with property data + computed fields to avoid N+1.

    Args:
        db: Database session
        city: Filter by city
        limit: Limit results
        offset: Offset results

    Returns:
        List of dicts with property data
    """
    start_time = time.time()

    # Subquery for latest price
    latest_price_subq = (
        select(PropertyPriceHistory.new_price)
        .where(PropertyPriceHistory.property_id == Property.id)
        .order_by(desc(PropertyPriceHistory.changed_at))
        .limit(1)
        .correlate(Property)
        .scalar_subquery()
    )

    # Subquery for view count
    threshold = datetime.utcnow() - timedelta(days=7)
    view_count_subq = (
        select(func.count(PropertyView.id))
        .where(
            and_(
                PropertyView.property_id == Property.id,
                PropertyView.viewed_at >= threshold
            )
        )
        .correlate(Property)
        .scalar_subquery()
    )

    # Build query
    filters = [Property.is_active == True]
    if city:
        filters.append(Property.city == city)

    query = (
        select(
            Property,
            latest_price_subq.label("latest_price"),
            view_count_subq.label("view_count")
        )
        .where(and_(*filters))
        .order_by(desc(Property.created_at))
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    rows = result.all()

    # Convert to dicts
    properties = []
    for row in rows:
        prop = row[0]
        prop_dict = prop.to_dict()
        prop_dict["latest_price"] = row[1]
        prop_dict["view_count_7d"] = row[2]
        properties.append(prop_dict)

    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT_ENRICHED", "properties", duration)

    logger.debug(f"Enriched query returned {len(properties)} properties in {duration:.3f}s")
    return properties


# ==================== Optimized Statistics ====================

async def get_statistics_optimized(
    db: AsyncSession,
    city: Optional[str] = None,
    source: Optional[str] = None,
    district: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get property statistics in single optimized query.

    Uses single SQL query with multiple aggregations.
    """
    start_time = time.time()

    filters = [Property.is_active == True]

    if city:
        filters.append(Property.city == city)
    if source:
        filters.append(Property.source == source)
    if district:
        filters.append(Property.district == district)

    # Single query with all aggregations
    result = await db.execute(
        select(
            func.count(Property.id).label("total"),
            func.avg(Property.price).label("avg_price"),
            func.min(Property.price).label("min_price"),
            func.max(Property.price).label("max_price"),
            func.avg(Property.area).label("avg_area"),
            func.avg(Property.rooms).label("avg_rooms"),
            func.avg(Property.price_per_sqm).label("avg_price_per_sqm"),
        ).where(and_(*filters))
    )

    row = result.one()

    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT_STATS", "properties", duration)

    return {
        "total": row.total,
        "avg_price": float(row.avg_price) if row.avg_price else None,
        "min_price": float(row.min_price) if row.min_price else None,
        "max_price": float(row.max_price) if row.max_price else None,
        "avg_area": float(row.avg_area) if row.avg_area else None,
        "avg_rooms": float(row.avg_rooms) if row.avg_rooms else None,
        "avg_price_per_sqm": float(row.avg_price_per_sqm) if row.avg_price_per_sqm else None,
    }


# ==================== Export helpers ====================

async def stream_properties_query(
    db: AsyncSession,
    city: Optional[str] = None,
    source: Optional[str] = None,
    is_active: bool = True
):
    """
    Create streaming query for large exports.

    Uses server-side cursor for memory-efficient streaming.
    """
    filters = [Property.is_active == is_active]

    if city:
        filters.append(Property.city == city)
    if source:
        filters.append(Property.source == source)

    query = select(Property).where(and_(*filters))

    return query
