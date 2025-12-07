"""
CRUD operations for Property model.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update, delete, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.property import Property, PropertyPriceHistory, PropertyView, SearchQuery
from app.models.schemas import PropertyCreate

logger = logging.getLogger(__name__)


# ==================== Property CRUD ====================

async def create_property(db: AsyncSession, property_data: PropertyCreate) -> Property:
    """Create a new property."""
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
    
    logger.info(f"Created property: {db_property.id} from {db_property.source}")
    return db_property


async def get_property(db: AsyncSession, property_id: int) -> Optional[Property]:
    """Get property by ID."""
    result = await db.execute(
        select(Property).where(Property.id == property_id)
    )
    return result.scalar_one_or_none()


async def get_property_by_external_id(
    db: AsyncSession, 
    source: str, 
    external_id: str
) -> Optional[Property]:
    """Get property by source and external ID."""
    result = await db.execute(
        select(Property).where(
            and_(
                Property.source == source,
                Property.external_id == external_id
            )
        )
    )
    return result.scalar_one_or_none()


async def update_property(
    db: AsyncSession,
    property_id: int,
    property_data: Dict[str, Any]
) -> Optional[Property]:
    """Update property fields."""
    await db.execute(
        update(Property)
        .where(Property.id == property_id)
        .values(**property_data, last_updated=datetime.utcnow())
    )
    return await get_property(db, property_id)


async def update_or_create_property(
    db: AsyncSession,
    property_data: PropertyCreate
) -> tuple[Property, bool]:
    """
    Update existing property or create new one.
    Returns (property, created) where created is True if new property was created.
    """
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
        logger.info(f"Updated property: {existing.id}")
        return existing, False
    else:
        new_property = await create_property(db, property_data)
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
    return list(result.scalars().all())


async def get_property_statistics(
    db: AsyncSession,
    city: Optional[str] = None,
    source: Optional[str] = None,
    district: Optional[str] = None
) -> Dict[str, Any]:
    """Get statistics for properties."""
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
    return list(result.scalars().all())


# ==================== Price History CRUD ====================

async def track_price_change(
    db: AsyncSession,
    property_id: int,
    old_price: float,
    new_price: float
) -> PropertyPriceHistory:
    """Track a price change."""
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
    
    logger.info(f"Tracked price change for property {property_id}: {old_price} -> {new_price}")
    return price_history


async def get_price_history(
    db: AsyncSession,
    property_id: int,
    limit: int = 10
) -> List[PropertyPriceHistory]:
    """Get price history for a property."""
    result = await db.execute(
        select(PropertyPriceHistory)
        .where(PropertyPriceHistory.property_id == property_id)
        .order_by(desc(PropertyPriceHistory.changed_at))
        .limit(limit)
    )
    return list(result.scalars().all())


# ==================== View Tracking CRUD ====================

async def track_property_view(
    db: AsyncSession,
    property_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    referer: Optional[str] = None
) -> PropertyView:
    """Track a property view."""
    view = PropertyView(
        property_id=property_id,
        ip_address=ip_address,
        user_agent=user_agent,
        referer=referer
    )
    
    db.add(view)
    await db.flush()
    
    return view


async def get_property_view_count(
    db: AsyncSession,
    property_id: int,
    days: int = 30
) -> int:
    """Get view count for a property in the last N days."""
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
    query_params = {
        "city": city,
        "property_type": property_type,
        "min_price": min_price,
        "max_price": max_price,
        "min_rooms": min_rooms,
        "max_rooms": max_rooms,
        "min_area": min_area,
        "max_area": max_area,
        **kwargs
    }
    
    search_query = SearchQuery(
        city=city,
        property_type=property_type,
        min_price=min_price,
        max_price=max_price,
        min_rooms=min_rooms,
        max_rooms=max_rooms,
        min_area=min_area,
        max_area=max_area,
        query_params=query_params,
        results_count=results_count,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    db.add(search_query)
    await db.flush()
    
    return search_query


async def get_popular_searches(
    db: AsyncSession,
    limit: int = 10,
    days: int = 7
) -> List[Dict[str, Any]]:
    """Get most popular search queries."""
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
    Bulk insert or update properties.
    Returns dict with counts of created and updated properties.
    """
    created = 0
    updated = 0
    errors = 0
    
    for property_data in properties:
        try:
            _, is_created = await update_or_create_property(db, property_data)
            if is_created:
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors += 1
            logger.error(f"Error upserting property {property_data.external_id}: {e}")
    
    await db.commit()
    
    logger.info(f"Bulk upsert completed: {created} created, {updated} updated, {errors} errors")
    
    return {
        "created": created,
        "updated": updated,
        "errors": errors
    }
