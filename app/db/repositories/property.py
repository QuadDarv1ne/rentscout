"""
CRUD operations for Property model.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update, delete, and_, or_, func, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.db.models.property import Property, PropertyPriceHistory, PropertyView, SearchQuery
from app.models.schemas import PropertyCreate
from app.utils.metrics import metrics_collector

logger = logging.getLogger(__name__)


# ==================== Property CRUD ====================

async def create_property(db: AsyncSession, property_data: PropertyCreate) -> Property:
    """Create a new property."""
    start_time = time.time()
    
    # Extract location fields if available
    location = property_data.location or {}
    
    property_dict = property_data.model_dump()
    
    db_property = Property(
        source=property_dict["source"],
        external_id=property_dict["external_id"],
        title=property_dict["title"],
        description=property_dict.get("description"),
        link=property_dict.get("link"),
        price=property_dict["price"],
        rooms=property_dict.get("rooms"),
        area=property_dict.get("area"),
        city=location.get("city"),
        district=location.get("district"),
        address=location.get("address"),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        location=location,
        photos=property_dict.get("photos", []),
    )
    
    db.add(db_property)
    await db.flush()
    await db.refresh(db_property)
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("INSERT", "properties", duration)
    metrics_collector.record_property_saved()
    
    logger.info(f"Created property: {db_property.id} from {db_property.source}")
    return db_property


async def bulk_create_properties(db: AsyncSession, properties_data: List[PropertyCreate]) -> List[Property]:
    """
    Create multiple properties in a single bulk operation for better performance.
    
    Args:
        db: Database session
        properties_data: List of property data to create
        
    Returns:
        List of created property objects
    """
    start_time = time.time()
    
    if not properties_data:
        return []
    
    # Convert PropertyCreate objects to dictionaries for bulk insert
    properties_dicts = []
    for prop_data in properties_data:
        location = prop_data.location or {}
        prop_dict = prop_data.model_dump()
        
        # Prepare the dictionary for bulk insert
        properties_dicts.append({
            "source": prop_dict["source"],
            "external_id": prop_dict["external_id"],
            "title": prop_dict["title"],
            "description": prop_dict.get("description"),
            "link": prop_dict.get("link"),
            "price": prop_dict["price"],
            "rooms": prop_dict.get("rooms"),
            "area": prop_dict.get("area"),
            "city": location.get("city"),
            "district": location.get("district"),
            "address": location.get("address"),
            "latitude": location.get("latitude"),
            "longitude": location.get("longitude"),
            "location": location,
            "photos": prop_dict.get("photos", []),
        })
    
    try:
        # Use PostgreSQL's INSERT ... ON CONFLICT DO NOTHING for deduplication
        stmt = insert(Property).values(properties_dicts)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=['source', 'external_id']
        )
        
        result = await db.execute(stmt)
        await db.flush()
        
        # Get the inserted/updated properties
        # For simplicity, we'll fetch them separately since bulk insert doesn't return objects
        external_ids = [prop.external_id for prop in properties_data]
        sources = [prop.source for prop in properties_data]
        
        query = select(Property).where(
            and_(
                Property.external_id.in_(external_ids),
                Property.source.in_(sources)
            )
        )
        result = await db.execute(query)
        created_properties = list(result.scalars().all())
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("BULK_INSERT", "properties", duration)
        metrics_collector.record_properties_saved(len(created_properties))
        
        logger.info(f"Bulk created {len(created_properties)} properties")
        return created_properties
        
    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_db_query("BULK_INSERT", "properties", duration, error=True)
        logger.error(f"Error bulk creating properties: {e}")
        raise


async def get_property(db: AsyncSession, property_id: int) -> Optional[Property]:
    """Get a property by ID."""
    start_time = time.time()
    
    query = select(Property).where(Property.id == property_id)
    result = await db.execute(query)
    property_obj = result.scalar_one_or_none()
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT", "properties", duration)
    
    return property_obj


async def get_property_by_external_id(
    db: AsyncSession, 
    source: str, 
    external_id: str
) -> Optional[Property]:
    """Get property by source and external ID."""
    start_time = time.time()
    
    result = await db.execute(
        select(Property).where(
            and_(
                Property.source == source,
                Property.external_id == external_id
            )
        )
    )
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT", "properties", duration)
    
    return result.scalar_one_or_none()


async def update_property(
    db: AsyncSession,
    property_id: int,
    property_data: Dict[str, Any]
) -> Optional[Property]:
    """Update property fields."""
    start_time = time.time()
    
    await db.execute(
        update(Property)
        .where(Property.id == property_id)
        .values(**property_data, last_updated=datetime.utcnow())
    )
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("UPDATE", "properties", duration)
    
    return await get_property(db, property_id)


async def update_or_create_property(
    db: AsyncSession,
    property_data: PropertyCreate
) -> tuple[Property, bool]:
    """
    Update existing property or create new one.
    Returns (property, created) where created is True if new property was created.
    """
    start_time = time.time()
    
    existing = await get_property_by_external_id(
        db,
        property_data.source,
        property_data.external_id
    )
    
    if existing:
        # Check if price changed
        if existing.price != property_data.price:
            await track_price_change(db, existing.id, existing.price, property_data.price)
        
        # Update last_seen and other fields
        property_dict = property_data.model_dump()
        location = property_dict.get("location", {})
        
        await db.execute(
            update(Property)
            .where(Property.id == existing.id)
            .values(
                title=property_dict["title"],
                description=property_dict.get("description"),
                price=property_dict["price"],
                rooms=property_dict.get("rooms"),
                area=property_dict.get("area"),
                city=location.get("city"),
                district=location.get("district"),
                address=location.get("address"),
                latitude=location.get("latitude"),
                longitude=location.get("longitude"),
                location=location,
                photos=property_dict.get("photos", []),
                last_seen=datetime.utcnow(),
                last_updated=datetime.utcnow()
            )
        )
        
        await db.refresh(existing)
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("UPDATE", "properties", duration)
        metrics_collector.record_property_processed(property_data.source, "updated")
        
        logger.info(f"Updated property: {existing.id}")
        return existing, False
    else:
        new_property = await create_property(db, property_data)
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("INSERT", "properties", duration)
        metrics_collector.record_property_processed(property_data.source, "created")
        
        return new_property, True


async def deactivate_old_properties(
    db: AsyncSession,
    source: str,
    hours: int = 24
) -> int:
    """
    Deactivate properties not seen in the last N hours.
    Returns count of deactivated properties.
    """
    start_time = time.time()
    
    threshold = datetime.utcnow() - timedelta(hours=hours)
    
    result = await db.execute(
        update(Property)
        .where(
            and_(
                Property.source == source,
                Property.last_seen < threshold,
                Property.is_active == True
            )
        )
        .values(is_active=False)
    )
    
    count = result.rowcount
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("UPDATE", "properties", duration)
    
    logger.info(f"Deactivated {count} properties from {source} not seen in {hours} hours")
    return count


async def search_properties(
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
    offset: int = 0
) -> List[Property]:
    """Search properties with filters."""
    start_time = time.time()
    
    query = select(Property)
    
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
        else:  # default to created_at
            query = query.order_by(desc(Property.created_at))
    else:  # asc
        if sort_by == "price":
            query = query.order_by(Property.price)
        elif sort_by == "area":
            query = query.order_by(Property.area)
        elif sort_by == "rooms":
            query = query.order_by(Property.rooms)
        else:  # default to created_at
            query = query.order_by(Property.created_at)
    
    # Apply pagination
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT", "properties", duration)
    
    return list(result.scalars().all())


async def get_property_statistics(
    db: AsyncSession,
    city: Optional[str] = None,
    source: Optional[str] = None,
    district: Optional[str] = None
) -> Dict[str, Any]:
    """Get statistics for properties."""
    start_time = time.time()
    
    filters = [Property.is_active == True]
    
    if city:
        filters.append(Property.city == city)
    if source:
        filters.append(Property.source == source)
    if district:
        filters.append(Property.district == district)
    
    # Use a single query with all aggregations
    result = await db.execute(
        select(
            func.count(Property.id).label("total"),
            func.avg(Property.price).label("avg_price"),
            func.min(Property.price).label("min_price"),
            func.max(Property.price).label("max_price"),
            func.avg(Property.area).label("avg_area"),
            func.min(Property.area).label("min_area"),
            func.max(Property.area).label("max_area"),
            func.avg(Property.rooms).label("avg_rooms"),
        ).where(and_(*filters))
    )
    
    row = result.one()
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT", "properties", duration)
    
    return {
        "total": row.total,
        "avg_price": float(row.avg_price) if row.avg_price else None,
        "min_price": float(row.min_price) if row.min_price else None,
        "max_price": float(row.max_price) if row.max_price else None,
        "avg_area": float(row.avg_area) if row.avg_area else None,
        "min_area": float(row.min_area) if row.min_area else None,
        "max_area": float(row.max_area) if row.max_area else None,
        "avg_rooms": float(row.avg_rooms) if row.avg_rooms else None,
    }


async def search_properties_by_price_per_sqm(
    db: AsyncSession,
    city: Optional[str] = None,
    source: Optional[str] = None,
    district: Optional[str] = None,
    max_price_per_sqm: Optional[float] = None,
    is_active: bool = True,
    limit: int = 100,
    offset: int = 0
) -> List[Property]:
    """Search properties with price per square meter filter."""
    start_time = time.time()
    
    query = select(Property)
    
    # Build filters
    filters = [Property.is_active == is_active] if is_active is not None else []
    
    if city:
        filters.append(Property.city == city)
    if source:
        filters.append(Property.source == source)
    if district:
        filters.append(Property.district == district)
    
    # Filter by price per square meter (only for properties with valid area)
    if max_price_per_sqm is not None:
        filters.append(and_(
            Property.area > 0,
            (Property.price / Property.area) <= max_price_per_sqm
        ))
    
    query = query.where(and_(*filters))
    query = query.order_by(Property.price / Property.area)  # Sort by price per sqm ascending
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT", "properties", duration)
    
    return list(result.scalars().all())


# ==================== Price History CRUD ====================

async def track_price_change(
    db: AsyncSession,
    property_id: int,
    old_price: float,
    new_price: float
) -> PropertyPriceHistory:
    """Track a price change."""
    start_time = time.time()
    
    price_change = new_price - old_price
    price_change_percent = (price_change / old_price * 100) if old_price > 0 else 0
    
    price_history = PropertyPriceHistory(
        property_id=property_id,
        old_price=old_price,
        new_price=new_price,
        price_change=price_change,
        price_change_percent=price_change_percent
    )
    
    db.add(price_history)
    await db.flush()
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("INSERT", "price_history", duration)
    
    logger.info(f"Tracked price change for property {property_id}: {old_price} -> {new_price}")
    return price_history


async def get_price_history(
    db: AsyncSession,
    property_id: int,
    limit: int = 10
) -> List[PropertyPriceHistory]:
    """Get price history for a property."""
    start_time = time.time()
    
    result = await db.execute(
        select(PropertyPriceHistory)
        .where(PropertyPriceHistory.property_id == property_id)
        .order_by(desc(PropertyPriceHistory.changed_at))
        .limit(limit)
    )
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT", "price_history", duration)
    
    return list(result.scalars().all())


async def get_price_trends(db: AsyncSession, city: str, days: int = 30) -> List[Dict[str, Any]]:
    """
    Get price trends for properties in a city over a period of days.
    
    Args:
        db: Database session
        city: City to get trends for
        days: Number of days to analyze
        
    Returns:
        List of daily price statistics
    """
    start_time = time.time()
    
    try:
        # Calculate the date threshold
        threshold_date = datetime.utcnow() - timedelta(days=days)
        
        # Query to get daily price averages
        query = (
            select(
                func.date(Property.created_at).label('date'),
                func.avg(Property.price).label('average_price'),
                func.count(Property.id).label('property_count'),
                func.min(Property.price).label('min_price'),
                func.max(Property.price).label('max_price')
            )
            .where(
                and_(
                    Property.city == city,
                    Property.created_at >= threshold_date,
                    Property.is_active == True
                )
            )
            .group_by(func.date(Property.created_at))
            .order_by(func.date(Property.created_at))
        )
        
        result = await db.execute(query)
        rows = result.all()
        
        # Convert to dictionary format
        trends = []
        for row in rows:
            trends.append({
                "date": row.date.isoformat() if row.date else None,
                "average_price": float(row.average_price) if row.average_price else 0,
                "property_count": row.property_count,
                "min_price": float(row.min_price) if row.min_price else 0,
                "max_price": float(row.max_price) if row.max_price else 0
            })
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("SELECT", "price_trends", duration)
        
        logger.info(f"Retrieved price trends for {city} over {days} days")
        return trends
        
    except Exception as e:
        duration = time.time() - start_time
        metrics_collector.record_db_query("SELECT", "price_trends", duration, error=True)
        logger.error(f"Error getting price trends: {e}")
        raise


# ==================== View Tracking CRUD ====================

async def track_property_view(
    db: AsyncSession,
    property_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    referer: Optional[str] = None
) -> PropertyView:
    """Track a property view."""
    start_time = time.time()
    
    view = PropertyView(
        property_id=property_id,
        ip_address=ip_address,
        user_agent=user_agent,
        referer=referer
    )
    
    db.add(view)
    await db.flush()
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("INSERT", "property_views", duration)
    
    return view


async def get_property_view_count(
    db: AsyncSession,
    property_id: int,
    days: int = 30
) -> int:
    """Get view count for a property in the last N days."""
    start_time = time.time()
    
    threshold = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(func.count(PropertyView.id))
        .where(
            and_(
                PropertyView.property_id == property_id,
                PropertyView.viewed_at >= threshold
            )
        )
    )
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT", "property_views", duration)
    
    return result.scalar_one()


async def get_popular_properties(
    db: AsyncSession,
    limit: int = 10,
    days: int = 7
) -> List[tuple[int, int]]:
    """
    Get most popular properties by view count.
    Returns list of (property_id, view_count) tuples.
    """
    start_time = time.time()
    
    threshold = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(
            PropertyView.property_id,
            func.count(PropertyView.id).label("view_count")
        )
        .where(PropertyView.viewed_at >= threshold)
        .group_by(PropertyView.property_id)
        .order_by(desc("view_count"))
        .limit(limit)
    )
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT", "property_views", duration)
    
    return [(row.property_id, row.view_count) for row in result.all()]


# ==================== Search Query Tracking CRUD ====================

async def track_search_query(
    db: AsyncSession,
    city: Optional[str] = None,
    property_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rooms: Optional[int] = None,
    max_rooms: Optional[int] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    results_count: int = 0,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    **kwargs
) -> SearchQuery:
    """Track a search query."""
    start_time = time.time()
    
    search_query = SearchQuery(
        city=city,
        property_type=property_type,
        min_price=min_price,
        max_price=max_price,
        rooms=min_rooms,  # Store min_rooms in rooms field for simplicity
        min_area=min_area,
        max_area=max_area,
        results_count=results_count,
        ip_address=ip_address
    )
    
    db.add(search_query)
    await db.flush()
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("INSERT", "search_queries", duration)
    
    return search_query


async def get_popular_searches(
    db: AsyncSession,
    limit: int = 10,
    days: int = 7
) -> List[Dict[str, Any]]:
    """Get most popular search queries."""
    start_time = time.time()
    
    threshold = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(
            SearchQuery.city,
            SearchQuery.property_type,
            func.count(SearchQuery.id).label("search_count")
        )
        .where(SearchQuery.searched_at >= threshold)
        .group_by(SearchQuery.city, SearchQuery.property_type)
        .order_by(desc("search_count"))
        .limit(limit)
    )
    
    # Record metrics
    duration = time.time() - start_time
    metrics_collector.record_db_query("SELECT", "search_queries", duration)
    
    return [
        {
            "city": row.city,
            "property_type": row.property_type,
            "count": row.search_count
        }
        for row in result.all()
    ]


# ==================== Bulk Operations ====================

async def bulk_upsert_properties(
    db: AsyncSession,
    properties: List[PropertyCreate]
) -> Dict[str, int]:
    """
    Bulk insert or update properties using efficient PostgreSQL UPSERT.
    Returns dict with counts of created and updated properties.
    """
    start_time = time.time()
    
    if not properties:
        return {"created": 0, "updated": 0, "errors": 0}
    
    try:
        # Convert PropertyCreate objects to dictionaries
        properties_dicts = []
        for prop_data in properties:
            location = prop_data.location or {}
            prop_dict = prop_data.model_dump()
            
            properties_dicts.append({
                "source": prop_dict["source"],
                "external_id": prop_dict["external_id"],
                "title": prop_dict["title"],
                "description": prop_dict.get("description"),
                "link": prop_dict.get("link"),
                "price": prop_dict["price"],
                "rooms": prop_dict.get("rooms"),
                "area": prop_dict.get("area"),
                "city": location.get("city"),
                "district": location.get("district"),
                "address": location.get("address"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "location": location,
                "photos": prop_dict.get("photos", []),
                "last_seen": datetime.utcnow(),
            })
        
        # Use PostgreSQL's INSERT ... ON CONFLICT DO UPDATE
        stmt = insert(Property).values(properties_dicts)
        stmt = stmt.on_conflict_do_update(
            index_elements=['source', 'external_id'],
            set_={
                'title': stmt.excluded.title,
                'description': stmt.excluded.description,
                'price': stmt.excluded.price,
                'rooms': stmt.excluded.rooms,
                'area': stmt.excluded.area,
                'city': stmt.excluded.city,
                'district': stmt.excluded.district,
                'address': stmt.excluded.address,
                'latitude': stmt.excluded.latitude,
                'longitude': stmt.excluded.longitude,
                'location': stmt.excluded.location,
                'photos': stmt.excluded.photos,
                'last_seen': stmt.excluded.last_seen,
                'last_updated': datetime.utcnow(),
            }
        )
        
        await db.execute(stmt)
        await db.commit()
        
        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("BULK_UPSERT", "properties", duration)
        metrics_collector.record_task_processed("bulk_upsert", "success")
        
        # Note: We can't easily distinguish created vs updated in bulk upsert
        # Return total count as created for simplicity
        logger.info(f"Bulk upsert completed: {len(properties)} properties processed")
        
        return {
            "created": len(properties),
            "updated": 0,
            "errors": 0
        }
        
    except Exception as e:
        await db.rollback()
        duration = time.time() - start_time
        metrics_collector.record_db_query("BULK_UPSERT", "properties", duration, error=True)
        metrics_collector.record_task_processed("bulk_upsert", "error")
        logger.error(f"Error in bulk upsert: {e}")
        
        return {
            "created": 0,
            "updated": 0,
            "errors": len(properties)
        }