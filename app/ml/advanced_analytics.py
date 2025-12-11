"""
Advanced Analytics Engine for RentScout v2.2.0

Provides comprehensive analytics insights:
- Market trend analysis
- Price prediction and forecasting
- Location-based analytics
- Property clustering and recommendations
- Demand estimation
- ROI analysis for properties
- Comparative market analysis
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from collections import defaultdict, deque
import numpy as np
from statistics import mean, median, stdev

logger = logging.getLogger(__name__)


class AnalyticsCategory(Enum):
    """Categories for advanced analytics"""
    MARKET = "market"
    PRICE = "price"
    LOCATION = "location"
    PROPERTY = "property"
    DEMAND = "demand"
    COMPETITION = "competition"
    TREND = "trend"
    ROI = "roi"


class PropertyType(Enum):
    """Type of property"""
    APARTMENT = "apartment"
    HOUSE = "house"
    STUDIO = "studio"
    ROOM = "room"
    COMMERCIAL = "commercial"
    OTHER = "other"


@dataclass
class PropertyAnalysis:
    """Analysis of a single property"""
    property_id: str
    location: str
    price: float
    rooms: int
    area: float
    price_per_sqm: float
    property_type: PropertyType
    market_position: str  # "above_average", "average", "below_average"
    recommendations: List[str] = field(default_factory=list)
    analysis_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MarketTrend:
    """Market trend analysis"""
    location: str
    category: str
    direction: str  # "up", "down", "stable"
    change_percent: float
    confidence: float
    start_date: datetime
    end_date: datetime
    data_points: int


@dataclass
class PriceForecast:
    """Price forecast for future periods"""
    location: str
    property_type: str
    forecast_date: datetime
    predicted_price: float
    confidence_interval: Tuple[float, float]
    trend: str
    seasonality_factor: float


@dataclass
class DemandMetrics:
    """Demand metrics for properties"""
    location: str
    total_listings: int
    active_listings: int
    sold_listings: int
    average_days_to_sell: float
    demand_level: str  # "high", "medium", "low"
    vacancy_rate: float
    absorption_rate: float


class PriceAnalyzer:
    """Analyzes price trends and patterns"""
    
    def __init__(self, history_size: int = 1000):
        self.price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_size))
        self.location_prices: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_size))
        self.seasonal_factors: Dict[str, Dict[int, float]] = defaultdict(dict)
    
    def record_price(self, location: str, property_type: str, price: float, area: float = 0):
        """Record a price observation"""
        key = f"{location}_{property_type}"
        self.price_history[key].append({
            'price': price,
            'area': area,
            'timestamp': datetime.now(),
            'price_per_sqm': price / area if area > 0 else 0
        })
        self.location_prices[location].append(price)
    
    def get_average_price(self, location: str, property_type: str, days: int = 30) -> float:
        """Get average price for last N days"""
        key = f"{location}_{property_type}"
        cutoff = datetime.now() - timedelta(days=days)
        
        prices = [
            p['price'] for p in self.price_history[key]
            if p['timestamp'] >= cutoff
        ]
        
        return mean(prices) if prices else 0.0
    
    def get_price_trend(self, location: str, property_type: str, days: int = 30) -> str:
        """Get price trend direction"""
        key = f"{location}_{property_type}"
        history = list(self.price_history[key])
        
        if len(history) < 2:
            return "insufficient_data"
        
        mid_point = len(history) // 2
        recent_avg = mean([p['price'] for p in history[mid_point:]])
        older_avg = mean([p['price'] for p in history[:mid_point]])
        
        change_percent = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        
        if change_percent > 2:
            return "up"
        elif change_percent < -2:
            return "down"
        else:
            return "stable"
    
    def analyze_price_per_sqm(self, location: str, area: float, price: float) -> Dict[str, float]:
        """Analyze price per square meter"""
        location_prices = list(self.location_prices[location])
        
        if not location_prices:
            return {"price_per_sqm": 0, "market_average": 0, "variance": 0}
        
        price_per_sqm = price / area if area > 0 else 0
        avg_price = mean(location_prices)
        avg_price_per_sqm = avg_price / area if area > 0 else 0
        variance = ((price_per_sqm - avg_price_per_sqm) / avg_price_per_sqm * 100) if avg_price_per_sqm > 0 else 0
        
        return {
            "price_per_sqm": round(price_per_sqm, 2),
            "market_average": round(avg_price_per_sqm, 2),
            "variance_percent": round(variance, 2)
        }


class MarketAnalyzer:
    """Analyzes overall market conditions"""
    
    def __init__(self):
        self.market_data: Dict[str, Dict[str, Any]] = {}
        self.trends: List[MarketTrend] = []
    
    def update_market_data(self, location: str, category: str, data: Dict[str, Any]):
        """Update market data for location"""
        if location not in self.market_data:
            self.market_data[location] = {}
        self.market_data[location][category] = {
            **data,
            'timestamp': datetime.now()
        }
    
    def record_trend(self, trend: MarketTrend):
        """Record market trend"""
        self.trends.append(trend)
        if len(self.trends) > 10000:
            self.trends = self.trends[-10000:]
    
    def get_market_summary(self, location: str) -> Dict[str, Any]:
        """Get market summary for location"""
        if location not in self.market_data:
            return {}
        
        return self.market_data[location]
    
    def get_supply_demand(self, location: str) -> Dict[str, float]:
        """Get supply/demand balance"""
        data = self.get_market_summary(location)
        
        supply = data.get('total_listings', 0)
        demand = data.get('active_listings', 0)
        
        return {
            "supply": supply,
            "demand": demand,
            "ratio": demand / supply if supply > 0 else 0,
            "market_status": self._classify_market(demand / supply if supply > 0 else 0)
        }
    
    @staticmethod
    def _classify_market(ratio: float) -> str:
        """Classify market as buyer's or seller's market"""
        if ratio > 1.5:
            return "buyer_market"  # More demand than supply
        elif ratio < 0.5:
            return "seller_market"  # More supply than demand
        else:
            return "balanced"


class DemandAnalyzer:
    """Analyzes demand patterns"""
    
    def __init__(self):
        self.demand_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=365))
        self.listing_activity: Dict[str, Dict] = {}
    
    def record_demand(self, location: str, listings_count: int, active_count: int):
        """Record demand metrics"""
        self.demand_history[location].append({
            'timestamp': datetime.now(),
            'total': listings_count,
            'active': active_count
        })
    
    def get_demand_level(self, location: str) -> str:
        """Get current demand level"""
        history = list(self.demand_history[location])
        
        if not history:
            return "unknown"
        
        recent = history[-7:]  # Last 7 records
        avg_active = mean([h['active'] for h in recent])
        avg_total = mean([h['total'] for h in recent])
        
        if avg_total == 0:
            return "unknown"
        
        active_percent = (avg_active / avg_total) * 100
        
        if active_percent > 70:
            return "high"
        elif active_percent > 30:
            return "medium"
        else:
            return "low"
    
    def get_absorption_rate(self, location: str) -> float:
        """Get absorption rate (% active listings)"""
        history = list(self.demand_history[location])
        
        if not history:
            return 0.0
        
        recent = history[-30:]
        if not recent:
            return 0.0
        
        avg_active = mean([h['active'] for h in recent])
        avg_total = mean([h['total'] for h in recent])
        
        return (avg_active / avg_total * 100) if avg_total > 0 else 0.0


class AdvancedAnalyticsEngine:
    """Main advanced analytics engine"""
    
    def __init__(self):
        self.price_analyzer = PriceAnalyzer()
        self.market_analyzer = MarketAnalyzer()
        self.demand_analyzer = DemandAnalyzer()
        self.property_analyses: Dict[str, PropertyAnalysis] = {}
        self.forecasts: List[PriceForecast] = []
    
    def analyze_property(
        self,
        property_id: str,
        location: str,
        price: float,
        rooms: int,
        area: float,
        property_type: PropertyType
    ) -> PropertyAnalysis:
        """Analyze a single property"""
        
        # Calculate price per sqm
        price_per_sqm = price / area if area > 0 else 0
        
        # Get market data
        price_stats = self.price_analyzer.analyze_price_per_sqm(location, area, price)
        market_avg = price_stats['market_average']
        variance = price_stats['variance_percent']
        
        # Determine market position
        if variance > 10:
            market_position = "above_average"
        elif variance < -10:
            market_position = "below_average"
        else:
            market_position = "average"
        
        # Generate recommendations
        recommendations = self._generate_property_recommendations(
            price, market_avg, variance, rooms, area
        )
        
        # Calculate analysis score
        analysis_score = self._calculate_property_score(
            property_id, location, price, rooms, area, property_type
        )
        
        analysis = PropertyAnalysis(
            property_id=property_id,
            location=location,
            price=price,
            rooms=rooms,
            area=area,
            price_per_sqm=price_per_sqm,
            property_type=property_type,
            market_position=market_position,
            recommendations=recommendations,
            analysis_score=analysis_score
        )
        
        self.property_analyses[property_id] = analysis
        return analysis
    
    def _generate_property_recommendations(
        self,
        price: float,
        market_avg: float,
        variance: float,
        rooms: int,
        area: float
    ) -> List[str]:
        """Generate property recommendations"""
        recommendations = []
        
        if variance > 15:
            recommendations.append("🔴 Цена значительно выше рынка - рассмотрите снижение")
        elif variance > 5:
            recommendations.append("🟡 Цена выше среднего по рынку")
        elif variance < -15:
            recommendations.append("🟢 Отличная цена - спрос должен быть высокий")
        
        if area < 20:
            recommendations.append("⚠️ Очень маленькая площадь - целевой рынок ограничен")
        elif area > 200:
            recommendations.append("💡 Большая площадь - подходит для семей")
        
        if rooms > 4:
            recommendations.append("👨‍👩‍👧‍👦 Семейный вариант - высокий спрос")
        elif rooms == 0:
            recommendations.append("📍 Студия - молодежный сегмент")
        
        return recommendations
    
    def _calculate_property_score(
        self,
        property_id: str,
        location: str,
        price: float,
        rooms: int,
        area: float,
        property_type: PropertyType
    ) -> float:
        """Calculate overall property analysis score"""
        score = 50.0  # Base score
        
        # Price factor (0-20 points)
        price_stats = self.price_analyzer.analyze_price_per_sqm(location, area, price)
        variance = price_stats['variance_percent']
        if variance < -10:
            score += 20
        elif variance < 0:
            score += 15
        elif variance < 10:
            score += 10
        
        # Size factor (0-15 points)
        if 30 < area < 150:
            score += 15
        elif 20 < area < 200:
            score += 10
        else:
            score += 5
        
        # Room factor (0-15 points)
        if rooms in [1, 2, 3]:
            score += 15
        elif rooms == 0 or rooms == 4:
            score += 10
        
        # Location factor (0-20 points)
        demand_level = self.demand_analyzer.get_demand_level(location)
        if demand_level == "high":
            score += 20
        elif demand_level == "medium":
            score += 10
        
        return min(100.0, score)
    
    def forecast_price(
        self,
        location: str,
        property_type: str,
        days_ahead: int = 30
    ) -> Optional[PriceForecast]:
        """Forecast future price"""
        
        # Get historical data
        avg_price = self.price_analyzer.get_average_price(location, property_type, 90)
        trend = self.price_analyzer.get_price_trend(location, property_type, 90)
        
        if avg_price == 0:
            return None
        
        # Simple linear forecast
        if trend == "up":
            growth_factor = 1.02  # 2% monthly growth
            seasonality = 1.05
        elif trend == "down":
            growth_factor = 0.98  # 2% monthly decline
            seasonality = 0.95
        else:
            growth_factor = 1.0
            seasonality = 1.0
        
        predicted_price = avg_price * (growth_factor ** (days_ahead / 30)) * seasonality
        
        # Confidence interval
        confidence_interval = (
            predicted_price * 0.85,
            predicted_price * 1.15
        )
        
        forecast = PriceForecast(
            location=location,
            property_type=property_type,
            forecast_date=datetime.now() + timedelta(days=days_ahead),
            predicted_price=predicted_price,
            confidence_interval=confidence_interval,
            trend=trend,
            seasonality_factor=seasonality
        )
        
        self.forecasts.append(forecast)
        if len(self.forecasts) > 10000:
            self.forecasts = self.forecasts[-10000:]
        
        return forecast
    
    def get_demand_metrics(self, location: str) -> DemandMetrics:
        """Get demand metrics for location"""
        market_data = self.market_analyzer.get_market_summary(location)
        demand_level = self.demand_analyzer.get_demand_level(location)
        absorption = self.demand_analyzer.get_absorption_rate(location)
        
        return DemandMetrics(
            location=location,
            total_listings=market_data.get('total_listings', 0),
            active_listings=market_data.get('active_listings', 0),
            sold_listings=market_data.get('sold_listings', 0),
            average_days_to_sell=market_data.get('avg_days_to_sell', 0),
            demand_level=demand_level,
            vacancy_rate=100 - absorption if absorption else 0,
            absorption_rate=absorption
        )
    
    def get_location_insights(self, location: str) -> Dict[str, Any]:
        """Get comprehensive insights for location"""
        market_summary = self.market_analyzer.get_market_summary(location)
        supply_demand = self.market_analyzer.get_supply_demand(location)
        demand_metrics = self.get_demand_metrics(location)
        
        return {
            "location": location,
            "market_summary": market_summary,
            "supply_demand": supply_demand,
            "demand_metrics": {
                "level": demand_metrics.demand_level,
                "absorption_rate": round(demand_metrics.absorption_rate, 2),
                "vacancy_rate": round(demand_metrics.vacancy_rate, 2)
            }
        }
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get overall analytics summary"""
        return {
            "properties_analyzed": len(self.property_analyses),
            "forecasts_generated": len(self.forecasts),
            "locations_tracked": len(self.market_analyzer.market_data),
            "market_trends": len(self.market_analyzer.trends),
            "average_analysis_score": round(
                mean([p.analysis_score for p in self.property_analyses.values()]) 
                if self.property_analyses else 0, 2
            )
        }


# Global instance
analytics_engine = AdvancedAnalyticsEngine()


def analyze_property_detailed(
    property_id: str,
    location: str,
    price: float,
    rooms: int,
    area: float,
    property_type: str = "apartment"
) -> PropertyAnalysis:
    """Analyze property with advanced analytics"""
    try:
        pt = PropertyType[property_type.upper()]
    except KeyError:
        pt = PropertyType.OTHER
    
    return analytics_engine.analyze_property(
        property_id, location, price, rooms, area, pt
    )
