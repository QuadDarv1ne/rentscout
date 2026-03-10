"""
Repository for materialized views.

Provides optimized queries using pre-computed aggregations.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_property_stats_by_location(
    db: AsyncSession,
    city: Optional[str] = None,
    district: Optional[str] = None,
    source: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get property statistics from materialized view.

    Much faster than querying properties table directly.
    """
    filters = []
    if city:
        filters.append(f"city = '{city}'")
    if district:
        filters.append(f"district = '{district}'")
    if source:
        filters.append(f"source = '{source}'")

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    query = text(f"""
        SELECT
            city,
            district,
            source,
            property_count,
            avg_price,
            min_price,
            max_price,
            avg_area,
            avg_rooms,
            avg_price_per_sqm,
            active_count,
            verified_count
        FROM mv_property_stats_by_location
        {where_clause}
        ORDER BY property_count DESC
    """)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "city": row.city,
            "district": row.district,
            "source": row.source,
            "property_count": row.property_count,
            "avg_price": float(row.avg_price) if row.avg_price else None,
            "min_price": float(row.min_price) if row.min_price else None,
            "max_price": float(row.max_price) if row.max_price else None,
            "avg_area": float(row.avg_area) if row.avg_area else None,
            "avg_rooms": float(row.avg_rooms) if row.avg_rooms else None,
            "avg_price_per_sqm": float(row.avg_price_per_sqm) if row.avg_price_per_sqm else None,
            "active_count": row.active_count,
            "verified_count": row.verified_count,
        }
        for row in rows
    ]


async def get_price_trends(
    db: AsyncSession,
    city: Optional[str] = None,
    rooms: Optional[int] = None,
    days: int = 30,
) -> List[Dict[str, Any]]:
    """
    Get price trends from materialized view.

    Returns daily price statistics.
    """
    date_filter = f"WHERE date >= CURRENT_DATE - INTERVAL '{days} days'"
    filters = [date_filter]

    if city:
        filters.append(f"city = '{city}'")
    if rooms is not None:
        filters.append(f"rooms = {rooms}")

    where_clause = " AND ".join(filters)

    query = text(f"""
        SELECT
            date,
            city,
            rooms,
            property_count,
            avg_price,
            min_price,
            max_price,
            avg_area,
            median_price
        FROM mv_price_trends_daily
        {where_clause}
        ORDER BY date DESC
    """)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "date": row.date.isoformat() if row.date else None,
            "city": row.city,
            "rooms": row.rooms,
            "property_count": row.property_count,
            "avg_price": float(row.avg_price) if row.avg_price else None,
            "min_price": float(row.min_price) if row.min_price else None,
            "max_price": float(row.max_price) if row.max_price else None,
            "avg_area": float(row.avg_area) if row.avg_area else None,
            "median_price": float(row.median_price) if row.median_price else None,
        }
        for row in rows
    ]


async def get_popular_searches(
    db: AsyncSession,
    city: Optional[str] = None,
    days: int = 7,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Get popular search queries from materialized view.
    """
    date_filter = f"WHERE search_date >= CURRENT_DATE - INTERVAL '{days} days'"
    filters = [date_filter]

    if city:
        filters.append(f"city = '{city}'")

    where_clause = " AND ".join(filters)

    query = text(f"""
        SELECT
            city,
            property_type,
            search_date,
            search_count,
            avg_results,
            unique_users
        FROM mv_popular_searches
        {where_clause}
        ORDER BY search_count DESC
        LIMIT {limit}
    """)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "city": row.city,
            "property_type": row.property_type,
            "search_date": row.search_date.isoformat() if row.search_date else None,
            "search_count": row.search_count,
            "avg_results": float(row.avg_results) if row.avg_results else None,
            "unique_users": row.unique_users,
        }
        for row in rows
    ]


async def get_property_view_stats(
    db: AsyncSession,
    property_id: Optional[int] = None,
    days: int = 7,
) -> List[Dict[str, Any]]:
    """
    Get property view statistics from materialized view.
    """
    date_filter = f"WHERE view_date >= CURRENT_DATE - INTERVAL '{days} days'"
    filters = [date_filter]

    if property_id:
        filters.append(f"property_id = {property_id}")

    where_clause = " AND ".join(filters)

    query = text(f"""
        SELECT
            property_id,
            view_date,
            view_count,
            unique_visitors
        FROM mv_property_views_daily
        {where_clause}
        ORDER BY view_date DESC, view_count DESC
    """)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "property_id": row.property_id,
            "view_date": row.view_date.isoformat() if row.view_date else None,
            "view_count": row.view_count,
            "unique_visitors": row.unique_visitors,
        }
        for row in rows
    ]


async def refresh_materialized_view(
    db: AsyncSession,
    view_name: str,
    concurrently: bool = False,
) -> bool:
    """
    Refresh a materialized view.

    Args:
        db: Database session
        view_name: Name of the materialized view
        concurrently: If True, allows concurrent access during refresh (requires unique index)

    Returns:
        True if successful
    """
    try:
        concurrently_str = "CONCURRENTLY" if concurrently else ""
        query = text(f"REFRESH MATERIALIZED VIEW {concurrently_str} {view_name}")
        await db.execute(query)
        await db.commit()
        return True
    except Exception as e:
        await db.rollback()
        raise e


async def get_all_materialized_views(db: AsyncSession) -> List[Dict[str, Any]]:
    """
    Get information about all materialized views.
    """
    query = text("""
        SELECT
            schemaname,
            matviewname as view_name,
            matviewowner as owner,
            hasindexes as has_indexes
        FROM pg_matviews
        WHERE schemaname = 'public'
        ORDER BY matviewname
    """)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "schema": row.schemaname,
            "view_name": row.view_name,
            "owner": row.owner,
            "has_indexes": row.has_indexes,
        }
        for row in rows
    ]
