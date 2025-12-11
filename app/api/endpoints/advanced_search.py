"""Advanced search endpoints."""
from fastapi import APIRouter, Query, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import Property
from app.utils.advanced_search import (
    AdvancedSearchEngine,
    SearchFilter,
    SortOrder
)
from app.services.search import SearchService
from app.utils.metrics import metrics_collector
from app.utils.property_scoring import PropertyScoringSystem
from app.db.models.session import get_db


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


class TopRatedPropertiesResponse(BaseModel):
    """Response for top rated properties."""
    property: Property
    score: Dict[str, float]
    rating: str


@router.post(
    "/properties/advanced-search",
    response_model=List[Property],
    summary="Advanced property search with filtering and ranking",
    description="Search properties with advanced filtering, sorting, and deduplication"
)
async def advanced_search(request: AdvancedSearchRequest, db: AsyncSession = Depends(get_db)):
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
    bucket_count: int = Query(default=10, ge=5, le=100),
    db: AsyncSession = Depends(get_db)
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
    property_type: str = Query(default="Квартира"),
    db: AsyncSession = Depends(get_db)
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


@router.get(
    "/properties/compare-cities",
    summary="Compare properties across multiple cities",
    description="Get comparative statistics for multiple cities"
)
async def compare_cities(
    cities: List[str] = Query(..., description="List of cities to compare"),
    property_type: str = Query(default="Квартира"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Compare property markets across multiple cities."""
    start_time = __import__('time').time()
    
    try:
        search_service = SearchService()
        comparison = {}
        
        for city in cities:
            properties = await search_service.search(city, property_type)
            
            if properties:
                prices = [p.price for p in properties if p.price]
                areas = [p.area for p in properties if p.area]
                
                comparison[city] = {
                    "total_count": len(properties),
                    "avg_price": sum(prices) / len(prices) if prices else None,
                    "min_price": min(prices) if prices else None,
                    "max_price": max(prices) if prices else None,
                    "avg_area": sum(areas) / len(areas) if areas else None,
                    "price_per_sqm": (
                        sum(p.price / p.area for p in properties if p.price and p.area and p.area > 0) /
                        len([p for p in properties if p.price and p.area and p.area > 0])
                    ) if any(p.price and p.area and p.area > 0 for p in properties) else None
                }
            else:
                comparison[city] = None
        
        # Find best value city
        valid_cities = {k: v for k, v in comparison.items() if v and v["price_per_sqm"]}
        if valid_cities:
            best_value_city = min(valid_cities.items(), key=lambda x: x[1]["price_per_sqm"])
            comparison["best_value"] = best_value_city[0]
        
        duration = __import__('time').time() - start_time
        metrics_collector.record_search_operation(",".join(cities), sum(1 for v in comparison.values() if v), duration)
        
        return comparison
    
    except Exception as e:
        metrics_collector.record_error("compare_cities")
        raise


@router.get(
    "/properties/{city}/top-rated",
    response_model=List[TopRatedPropertiesResponse],
    summary="Get top-rated properties by scoring system",
    description="Get best value properties based on comprehensive scoring"
)
async def get_top_rated_properties(
    city: str,
    property_type: str = Query(default="Квартира"),
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> List[TopRatedPropertiesResponse]:
    """Get top-rated properties using scoring system."""
    start_time = __import__('time').time()
    
    try:
        # Fetch properties
        search_service = SearchService()
        properties = await search_service.search(city, property_type)
        
        if not properties:
            return []
        
        # Rank properties using the enhanced scoring system
        ranked = PropertyScoringSystem.rank_properties(properties)
        
        # Get top N
        top_properties = ranked[:limit]
        
        # Format results
        results = []
        for prop, score in top_properties:
            results.append(TopRatedPropertiesResponse(
                property=prop,
                score=score.to_dict(),
                rating=PropertyScoringSystem.get_value_rating(score)
            ))
        
        duration = __import__('time').time() - start_time
        metrics_collector.record_search_operation(city, len(results), duration)
        
        return results
    
    except Exception as e:
        metrics_collector.record_error("top_rated_properties")
        raise