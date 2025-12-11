"""
API endpoints for Advanced Analytics

Provides comprehensive market analysis, price forecasting, and insights.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.ml.advanced_analytics import analytics_engine, PropertyType

router = APIRouter()


# ==================== Pydantic Models ====================

class PropertyRecommendation(BaseModel):
    """Recommendation for a property"""
    property_id: str
    location: str
    price: float
    price_per_sqm: float
    rooms: int
    area: float
    market_position: str
    analysis_score: float
    recommendations: List[str]
    timestamp: str


class PriceForecastResponse(BaseModel):
    """Price forecast response"""
    location: str
    property_type: str
    forecast_date: str
    predicted_price: float
    confidence_lower: float
    confidence_upper: float
    trend: str
    seasonality_factor: float


class DemandMetricsResponse(BaseModel):
    """Demand metrics response"""
    location: str
    total_listings: int
    active_listings: int
    sold_listings: int
    average_days_to_sell: float
    demand_level: str
    vacancy_rate: float
    absorption_rate: float


class LocationInsights(BaseModel):
    """Location insights"""
    location: str
    market_status: str  # buyer_market, seller_market, balanced
    supply_demand_ratio: float
    demand_level: str
    absorption_rate: float
    vacancy_rate: float
    average_price_per_sqm: float


class AnalyticsSummary(BaseModel):
    """Overall analytics summary"""
    properties_analyzed: int
    forecasts_generated: int
    locations_tracked: int
    market_trends: int
    average_analysis_score: float
    timestamp: str


# ==================== API Endpoints ====================

@router.post("/api/analytics/property/analyze")
async def analyze_property(
    property_id: str = Query(..., description="Property ID"),
    location: str = Query(..., description="Property location"),
    price: float = Query(..., gt=0, description="Property price"),
    rooms: int = Query(..., ge=0, description="Number of rooms"),
    area: float = Query(..., gt=0, description="Property area in sqm"),
    property_type: str = Query("apartment", description="Type of property")
) -> PropertyRecommendation:
    """
    Analyze a property with advanced analytics
    
    Provides market position, recommendations, and analysis score.
    """
    try:
        analysis = analytics_engine.analyze_property(
            property_id=property_id,
            location=location,
            price=price,
            rooms=rooms,
            area=area,
            property_type=PropertyType[property_type.upper()] if property_type else PropertyType.APARTMENT
        )
        
        return PropertyRecommendation(
            property_id=analysis.property_id,
            location=analysis.location,
            price=round(analysis.price, 2),
            price_per_sqm=round(analysis.price_per_sqm, 2),
            rooms=analysis.rooms,
            area=round(analysis.area, 2),
            market_position=analysis.market_position,
            analysis_score=round(analysis.analysis_score, 2),
            recommendations=analysis.recommendations,
            timestamp=analysis.timestamp.isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/property/{property_id}")
async def get_property_analysis(property_id: str) -> Optional[PropertyRecommendation]:
    """
    Get analysis for previously analyzed property
    
    Args:
        property_id: ID of property to retrieve analysis for
    
    Returns:
        Stored analysis or null if not found
    """
    try:
        analysis = analytics_engine.property_analyses.get(property_id)
        
        if not analysis:
            raise HTTPException(status_code=404, detail=f"No analysis for property {property_id}")
        
        return PropertyRecommendation(
            property_id=analysis.property_id,
            location=analysis.location,
            price=round(analysis.price, 2),
            price_per_sqm=round(analysis.price_per_sqm, 2),
            rooms=analysis.rooms,
            area=round(analysis.area, 2),
            market_position=analysis.market_position,
            analysis_score=round(analysis.analysis_score, 2),
            recommendations=analysis.recommendations,
            timestamp=analysis.timestamp.isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/analytics/price/forecast")
async def forecast_price(
    location: str = Query(..., description="Location to forecast"),
    property_type: str = Query("apartment", description="Type of property"),
    days_ahead: int = Query(30, ge=1, le=365, description="Days ahead to forecast")
) -> PriceForecastResponse:
    """
    Forecast future prices for a location
    
    Args:
        location: Location to forecast for
        property_type: Type of property
        days_ahead: Number of days ahead (1-365)
    
    Returns:
        Price forecast with confidence intervals
    """
    try:
        forecast = analytics_engine.forecast_price(
            location=location,
            property_type=property_type,
            days_ahead=days_ahead
        )
        
        if not forecast:
            raise HTTPException(status_code=404, detail=f"Insufficient data for forecast in {location}")
        
        return PriceForecastResponse(
            location=forecast.location,
            property_type=forecast.property_type,
            forecast_date=forecast.forecast_date.isoformat(),
            predicted_price=round(forecast.predicted_price, 2),
            confidence_lower=round(forecast.confidence_interval[0], 2),
            confidence_upper=round(forecast.confidence_interval[1], 2),
            trend=forecast.trend,
            seasonality_factor=round(forecast.seasonality_factor, 3)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/demand/{location}")
async def get_demand_metrics(location: str) -> DemandMetricsResponse:
    """
    Get demand metrics for location
    
    Args:
        location: Location to analyze
    
    Returns:
        Demand metrics and analysis
    """
    try:
        metrics = analytics_engine.get_demand_metrics(location)
        
        return DemandMetricsResponse(
            location=metrics.location,
            total_listings=metrics.total_listings,
            active_listings=metrics.active_listings,
            sold_listings=metrics.sold_listings,
            average_days_to_sell=round(metrics.average_days_to_sell, 1),
            demand_level=metrics.demand_level,
            vacancy_rate=round(metrics.vacancy_rate, 2),
            absorption_rate=round(metrics.absorption_rate, 2)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/location/{location}/insights")
async def get_location_insights(location: str) -> Dict:
    """
    Get comprehensive insights for location
    
    Args:
        location: Location to analyze
    
    Returns:
        Market summary, supply/demand, and trend analysis
    """
    try:
        insights = analytics_engine.get_location_insights(location)
        
        # Get supply/demand info
        supply_demand = analytics_engine.market_analyzer.get_supply_demand(location)
        
        return {
            "location": location,
            "timestamp": datetime.now().isoformat(),
            "market": {
                "status": supply_demand['market_status'],
                "supply": supply_demand['supply'],
                "demand": supply_demand['demand'],
                "ratio": round(supply_demand['ratio'], 2)
            },
            "demand": {
                "level": insights['demand_metrics']['level'],
                "absorption_rate": insights['demand_metrics']['absorption_rate'],
                "vacancy_rate": insights['demand_metrics']['vacancy_rate']
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/comparison/locations")
async def compare_locations(
    location1: str = Query(..., description="First location"),
    location2: str = Query(..., description="Second location")
) -> Dict:
    """
    Compare two locations
    
    Args:
        location1: First location to compare
        location2: Second location to compare
    
    Returns:
        Comparative analysis
    """
    try:
        insights1 = analytics_engine.get_location_insights(location1)
        insights2 = analytics_engine.get_location_insights(location2)
        
        demand1 = analytics_engine.get_demand_metrics(location1)
        demand2 = analytics_engine.get_demand_metrics(location2)
        
        return {
            "location1": {
                "name": location1,
                "demand_level": demand1.demand_level,
                "absorption_rate": round(demand1.absorption_rate, 2),
                "vacancy_rate": round(demand1.vacancy_rate, 2)
            },
            "location2": {
                "name": location2,
                "demand_level": demand2.demand_level,
                "absorption_rate": round(demand2.absorption_rate, 2),
                "vacancy_rate": round(demand2.vacancy_rate, 2)
            },
            "comparison": {
                "demand_difference": demand1.demand_level != demand2.demand_level,
                "more_active": location1 if demand1.active_listings > demand2.active_listings else location2,
                "faster_absorption": location1 if demand1.absorption_rate > demand2.absorption_rate else location2
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/analytics/market/record-price")
async def record_market_price(
    location: str = Query(..., description="Location"),
    property_type: str = Query("apartment", description="Property type"),
    price: float = Query(..., gt=0, description="Price"),
    area: float = Query(..., gt=0, description="Area in sqm")
) -> Dict:
    """
    Record price for market analysis
    
    Helps build price history for better forecasts.
    """
    try:
        analytics_engine.price_analyzer.record_price(
            location=location,
            property_type=property_type,
            price=price,
            area=area
        )
        
        return {
            "status": "recorded",
            "location": location,
            "property_type": property_type,
            "price": round(price, 2),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/summary")
async def get_analytics_summary() -> AnalyticsSummary:
    """
    Get overall analytics system summary
    
    Returns statistics about analyzed properties, forecasts, and locations.
    """
    try:
        summary = analytics_engine.get_analytics_summary()
        
        return AnalyticsSummary(
            properties_analyzed=summary['properties_analyzed'],
            forecasts_generated=summary['forecasts_generated'],
            locations_tracked=summary['locations_tracked'],
            market_trends=summary['market_trends'],
            average_analysis_score=summary['average_analysis_score'],
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/top-locations")
async def get_top_locations(limit: int = Query(10, ge=1, le=50)) -> Dict:
    """
    Get top locations by demand and activity
    
    Args:
        limit: Number of locations to return
    
    Returns:
        Top locations ranked by demand
    """
    try:
        locations_data = []
        
        for location in analytics_engine.market_analyzer.market_data.keys():
            demand = analytics_engine.get_demand_metrics(location)
            locations_data.append({
                "location": location,
                "active_listings": demand.active_listings,
                "demand_level": demand.demand_level,
                "absorption_rate": round(demand.absorption_rate, 2)
            })
        
        # Sort by active listings
        locations_data.sort(key=lambda x: x['active_listings'], reverse=True)
        
        return {
            "count": len(locations_data[:limit]),
            "locations": locations_data[:limit]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/analytics/market/update-data")
async def update_market_data(
    location: str = Query(..., description="Location"),
    category: str = Query(..., description="Data category"),
    total_listings: int = Query(..., ge=0),
    active_listings: int = Query(..., ge=0),
    sold_listings: int = Query(..., ge=0),
    avg_days_to_sell: float = Query(0, ge=0)
) -> Dict:
    """
    Update market data for location
    
    Records market metrics for trend analysis.
    """
    try:
        analytics_engine.market_analyzer.update_market_data(
            location=location,
            category=category,
            data={
                'total_listings': total_listings,
                'active_listings': active_listings,
                'sold_listings': sold_listings,
                'avg_days_to_sell': avg_days_to_sell
            }
        )
        
        analytics_engine.demand_analyzer.record_demand(
            location=location,
            listings_count=total_listings,
            active_count=active_listings
        )
        
        return {
            "status": "updated",
            "location": location,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/health")
async def analytics_health() -> Dict:
    """
    Check health of analytics system
    
    Returns status and data collection statistics.
    """
    summary = analytics_engine.get_analytics_summary()
    
    return {
        "status": "healthy",
        "system": "advanced_analytics_engine",
        "version": "1.0",
        "properties_analyzed": summary['properties_analyzed'],
        "locations_tracked": summary['locations_tracked'],
        "forecasts_generated": summary['forecasts_generated'],
        "timestamp": datetime.now().isoformat()
    }
