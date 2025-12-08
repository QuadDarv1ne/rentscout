"""Advanced search endpoints."""
from fastapi import APIRouter, Query
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.schemas import Property
from app.utils.advanced_search import (
    AdvancedSearchEngine,
    SearchFilter,
    SortOrder
)
from app.services.search import SearchService
from app.utils.metrics import metrics_collector


router = APIRouter()


class AdvancedSearchRequest(BaseModel):
    """Advanced search request parameters."""
    city: str = Field(..., description="City to search in")
    property_type: str = Field(default="Квартира", description="Property type")
    min_price: Optional[float] = Field(None, ge=0, description="Minimum price")
    max_price: Optional[float] = Field(None, ge=0, description="Maximum price")
    min_rooms: Optional[int] = Field(None, ge=0, description="Minimum rooms")
    max_rooms: Optional[int] = Field(None, ge=0, description="Maximum rooms")
    min_area: Optional[float] = Field(None, ge=0, description="Minimum area (m²)")
    max_area: Optional[float] = Field(None, ge=0, description="Maximum area (m²)")
    sort_by: str = Field(default="price", description="Sort by: price, area, rooms, price_per_area")
    sort_order: SortOrder = Field(default=SortOrder.ASC, description="Sort order: asc or desc")
    limit: int = Field(default=50, ge=1, le=1000, description="Results limit")


class PriceDistributionResponse(BaseModel):
    """Price distribution response."""
    count: int = Field(..., description="Number of properties")
    min: Optional[float] = Field(..., description="Minimum price")
    max: Optional[float] = Field(..., description="Maximum price")
    avg: Optional[float] = Field(..., description="Average price")
    median: Optional[float] = Field(..., description="Median price")
    distribution: List[int] = Field(..., description="Price distribution buckets")


@router.post(
    "/properties/advanced-search",
    response_model=List[Property],
    summary="Advanced property search with filtering and ranking",
    description="Search properties with advanced filtering, sorting, and deduplication"
)
async def advanced_search(request: AdvancedSearchRequest):
    """Advanced search with filtering and ranking."""
    start_time = __import__('time').time()
    
    try:
        # Fetch properties
        search_service = SearchService()
        properties = await search_service.search(request.city, request.property_type)
        
        # Create filter
        search_filter = SearchFilter(
            min_price=request.min_price,
            max_price=request.max_price,
            min_rooms=request.min_rooms,
            max_rooms=request.max_rooms,
            min_area=request.min_area,
            max_area=request.max_area,
            cities=[request.city] if request.city else None
        )
        
        # Apply filtering
        filtered = AdvancedSearchEngine.filter_properties(properties, search_filter)
        
        # Remove duplicates
        deduplicated = AdvancedSearchEngine.deduplicate_properties(filtered)
        
        # Apply ranking
        ranked = AdvancedSearchEngine.rank_properties(
            deduplicated,
            sort_by=request.sort_by,
            order=request.sort_order
        )
        
        # Limit results
        results = ranked[:request.limit]
        
        # Record metrics
        duration = __import__('time').time() - start_time
        metrics_collector.record_search_operation(request.city, len(results), duration)
        
        return results
    
    except Exception as e:
        metrics_collector.record_error("advanced_search")
        raise


@router.get(
    "/properties/{city}/price-distribution",
    response_model=PriceDistributionResponse,
    summary="Get price distribution for a city",
    description="Analyze price distribution of properties in a city"
)
async def get_price_distribution(
    city: str,
    property_type: str = Query(default="Квартира"),
    bucket_count: int = Query(default=10, ge=5, le=100)
):
    """Get price distribution statistics for a city."""
    start_time = __import__('time').time()
    
    try:
        # Fetch properties
        search_service = SearchService()
        properties = await search_service.search(city, property_type)
        
        # Get distribution
        distribution = AdvancedSearchEngine.get_price_distribution(
            properties,
            bucket_count=bucket_count
        )
        
        # Record metrics
        duration = __import__('time').time() - start_time
        metrics_collector.record_search_operation(city, distribution.get("count", 0), duration)
        
        return PriceDistributionResponse(**distribution)
    
    except Exception as e:
        metrics_collector.record_error("price_distribution")
        raise


@router.get(
    "/properties/{city}/statistics",
    summary="Get property statistics for a city",
    description="Get market statistics including avg price, area, rooms"
)
async def get_city_statistics(
    city: str,
    property_type: str = Query(default="Квартира")
):
    """Get comprehensive statistics for properties in a city."""
    start_time = __import__('time').time()
    
    try:
        # Fetch properties
        search_service = SearchService()
        properties = await search_service.search(city, property_type)
        
        if not properties:
            return {
                "city": city,
                "property_type": property_type,
                "total_count": 0,
                "sources": [],
                "price": {"min": None, "max": None, "avg": None},
                "area": {"min": None, "max": None, "avg": None},
                "rooms": {"min": None, "max": None, "avg": None}
            }
        
        # Calculate statistics
        prices = [p.price for p in properties if p.price]
        areas = [p.area for p in properties if p.area]
        rooms = [p.rooms for p in properties if p.rooms]
        sources = list(set(p.source for p in properties))
        
        stats = {
            "city": city,
            "property_type": property_type,
            "total_count": len(properties),
            "sources": sources,
            "price": {
                "min": min(prices) if prices else None,
                "max": max(prices) if prices else None,
                "avg": sum(prices) / len(prices) if prices else None,
                "count": len(prices)
            },
            "area": {
                "min": min(areas) if areas else None,
                "max": max(areas) if areas else None,
                "avg": sum(areas) / len(areas) if areas else None,
                "count": len(areas)
            },
            "rooms": {
                "min": min(rooms) if rooms else None,
                "max": max(rooms) if rooms else None,
                "avg": sum(rooms) / len(rooms) if rooms else None,
                "count": len(rooms)
            }
        }
        
        # Record metrics
        duration = __import__('time').time() - start_time
        metrics_collector.record_search_operation(city, len(properties), duration)
        
        return stats
    
    except Exception as e:
        metrics_collector.record_error("city_statistics")
        raise
