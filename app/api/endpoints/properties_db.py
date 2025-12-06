"""
API endpoints for property management with PostgreSQL persistence.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import get_db
from app.db.repositories import property as property_repo
from app.models.schemas import PropertyCreate, Property

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/properties", tags=["properties"])


@router.post("/", response_model=Property, status_code=201)
async def create_property(
    property_data: PropertyCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new property."""
    try:
        db_property = await property_repo.create_property(db, property_data)
        return db_property
    except Exception as e:
        logger.error(f"Error creating property: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{property_id}", response_model=Property)
async def get_property(
    property_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get property by ID."""
    db_property = await property_repo.get_property(db, property_id)
    
    if not db_property:
        raise HTTPException(status_code=404, detail="Property not found")
    
    return db_property


@router.get("/", response_model=List[Property])
async def search_properties(
    city: Optional[str] = Query(None, description="Filter by city"),
    source: Optional[str] = Query(None, description="Filter by source (avito, cian, etc.)"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    min_rooms: Optional[int] = Query(None, description="Minimum number of rooms"),
    max_rooms: Optional[int] = Query(None, description="Maximum number of rooms"),
    min_area: Optional[float] = Query(None, description="Minimum area in sq meters"),
    max_area: Optional[float] = Query(None, description="Maximum area in sq meters"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """
    Search properties with various filters.
    
    Supports filtering by:
    - City
    - Source (avito, cian, etc.)
    - Price range
    - Number of rooms
    - Area
    - Active status
    """
    try:
        properties = await property_repo.search_properties(
            db=db,
            city=city,
            min_price=min_price,
            max_price=max_price,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            min_area=min_area,
            max_area=max_area,
            source=source,
            is_active=is_active,
            limit=limit,
            offset=offset
        )
        
        # Track search query for analytics
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            await property_repo.track_search_query(
                db=db,
                city=city,
                min_price=min_price,
                max_price=max_price,
                min_rooms=min_rooms,
                max_rooms=max_rooms,
                min_area=min_area,
                max_area=max_area,
                results_count=len(properties),
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        return properties
    except Exception as e:
        logger.error(f"Error searching properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/overview")
async def get_statistics(
    city: Optional[str] = Query(None, description="Filter by city"),
    source: Optional[str] = Query(None, description="Filter by source"),
    db: AsyncSession = Depends(get_db)
):
    """Get property statistics."""
    try:
        stats = await property_repo.get_property_statistics(
            db=db,
            city=city,
            source=source
        )
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{property_id}/price-history")
async def get_price_history(
    property_id: int,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get price history for a property."""
    try:
        history = await property_repo.get_price_history(db, property_id, limit)
        return history
    except Exception as e:
        logger.error(f"Error getting price history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{property_id}/view")
async def track_view(
    property_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Track a property view."""
    try:
        # Verify property exists
        db_property = await property_repo.get_property(db, property_id)
        if not db_property:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Track the view
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        referer = request.headers.get("referer")
        
        await property_repo.track_property_view(
            db=db,
            property_id=property_id,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer
        )
        
        return {"status": "ok", "message": "View tracked"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking view: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/popular")
async def get_popular_properties(
    limit: int = Query(10, ge=1, le=100),
    days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get most popular properties by view count."""
    try:
        popular = await property_repo.get_popular_properties(db, limit, days)
        
        # Get full property data
        result = []
        for property_id, view_count in popular:
            db_property = await property_repo.get_property(db, property_id)
            if db_property:
                result.append({
                    "property": db_property,
                    "view_count": view_count
                })
        
        return result
    except Exception as e:
        logger.error(f"Error getting popular properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/searches")
async def get_popular_searches(
    limit: int = Query(10, ge=1, le=100),
    days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get most popular search queries."""
    try:
        searches = await property_repo.get_popular_searches(db, limit, days)
        return searches
    except Exception as e:
        logger.error(f"Error getting popular searches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk", status_code=201)
async def bulk_upsert_properties(
    properties: List[PropertyCreate],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk insert or update properties.
    Updates existing properties (matched by source + external_id) or creates new ones.
    """
    try:
        result = await property_repo.bulk_upsert_properties(db, properties)
        return result
    except Exception as e:
        logger.error(f"Error bulk upserting properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deactivate-old")
async def deactivate_old_properties(
    source: str = Query(..., description="Source to deactivate from"),
    hours: int = Query(24, ge=1, le=720, description="Hours since last seen"),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate properties not seen in the last N hours."""
    try:
        count = await property_repo.deactivate_old_properties(db, source, hours)
        return {"status": "ok", "deactivated_count": count}
    except Exception as e:
        logger.error(f"Error deactivating old properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))
