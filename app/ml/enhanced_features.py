"""
Enhanced ML features for price prediction.

Добавляет дополнительные признаки для улучшения качества предсказаний:
- Геолокация и инфраструктура
- Время года и день недели
- Динамика рынка
- Транспортная доступность
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import math


@dataclass
class EnhancedFeatures:
    """Расширенные признаки для ML модели."""
    # Временные признаки
    month: int
    day_of_week: int
    is_weekend: bool
    is_holiday_season: bool
    quarter: int

    # Инфраструктура
    metro_distance: Optional[float]  # км до ближайшего метро
    schools_count: int  # количество школ nearby
    shops_count: int  # количество магазинов nearby
    parks_count: int  # количество парков nearby

    # Транспорт
    transport_accessibility: float  # 0-1 индекс доступности

    # Рыночные признаки
    market_trend: float  # -1 до 1
    supply_demand_ratio: float  # отношение предложения к спросу
    neighborhood_avg_price: float  # средняя цена в районе

    # Качество жилья
    building_age: Optional[int]  # возраст здания
    renovation_year: Optional[int]  # год ремонта
    has_balcony: bool
    has_parking: bool
    has_elevator: bool

    # Экология
    ecology_score: float  # 0-10
    noise_level: float  # 0-10

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "month": self.month,
            "day_of_week": self.day_of_week,
            "is_weekend": self.is_weekend,
            "is_holiday_season": self.is_holiday_season,
            "quarter": self.quarter,
            "metro_distance": self.metro_distance,
            "schools_count": self.schools_count,
            "shops_count": self.shops_count,
            "parks_count": self.parks_count,
            "transport_accessibility": self.transport_accessibility,
            "market_trend": self.market_trend,
            "supply_demand_ratio": self.supply_demand_ratio,
            "neighborhood_avg_price": self.neighborhood_avg_price,
            "building_age": self.building_age,
            "renovation_year": self.renovation_year,
            "has_balcony": self.has_balcony,
            "has_parking": self.has_parking,
            "has_elevator": self.has_elevator,
            "ecology_score": self.ecology_score,
            "noise_level": self.noise_level,
        }


class EnhancedFeatureExtractor:
    """
    Извлечение расширенных признаков для ML модели.

    Использует открытые данные и эвристики для вычисления признаков.
    """

    # Данные по инфраструктуре районов (пример)
    DISTRICT_INFRASTRUCTURE: Dict[str, Dict[str, Any]] = {
        "Москва": {
            "Центральный": {
                "metro_density": 0.9,
                "schools_avg": 15,
                "shops_avg": 100,
                "parks_avg": 5,
                "transport_score": 0.95,
                "ecology_score": 5.5,
                "noise_level": 8.0,
            },
            "Таганский": {
                "metro_density": 0.7,
                "schools_avg": 10,
                "shops_avg": 50,
                "parks_avg": 3,
                "transport_score": 0.8,
                "ecology_score": 6.5,
                "noise_level": 6.0,
            },
            "Хамовники": {
                "metro_density": 0.6,
                "schools_avg": 12,
                "shops_avg": 40,
                "parks_avg": 8,
                "transport_score": 0.75,
                "ecology_score": 7.5,
                "noise_level": 5.0,
            },
        },
        "Санкт-Петербург": {
            "Центральный": {
                "metro_density": 0.8,
                "schools_avg": 12,
                "shops_avg": 80,
                "parks_avg": 6,
                "transport_score": 0.9,
                "ecology_score": 6.0,
                "noise_level": 7.5,
            },
        },
    }

    # Сезонные коэффициенты
    SEASONAL_FACTORS = {
        1: 0.95,   # Январь - низкий сезон
        2: 0.93,   # Февраль
        3: 0.97,   # Март
        4: 1.0,    # Апрель
        5: 1.05,   # Май
        6: 1.08,   # Июнь
        7: 1.1,    # Июль - высокий сезон
        8: 1.08,   # Август
        9: 1.05,   # Сентябрь
        10: 1.02,  # Октябрь
        11: 0.98,  # Ноябрь
        12: 0.95,  # Декабрь
    }

    @classmethod
    def extract_temporal_features(cls, date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Извлечь временные признаки.

        Returns:
            Dictionary with temporal features
        """
        if date is None:
            date = datetime.now()

        month = date.month
        day_of_week = date.weekday()  # 0 = Monday, 6 = Sunday
        is_weekend = day_of_week >= 5
        quarter = (month - 1) // 3 + 1

        # Holiday season (December holidays, summer vacations)
        is_holiday_season = (
            month == 12 or  # December holidays
            month == 1 or   # New Year
            (month >= 6 and month <= 8)  # Summer
        )

        seasonal_factor = cls.SEASONAL_FACTORS.get(month, 1.0)

        return {
            "month": month,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "is_holiday_season": is_holiday_season,
            "quarter": quarter,
            "seasonal_factor": seasonal_factor,
        }

    @classmethod
    def extract_location_features(
        cls,
        city: str,
        district: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Извлечь признаки локации.

        Использует данные об инфраструктуре района.
        """
        default_features = {
            "metro_density": 0.5,
            "schools_avg": 8,
            "shops_avg": 30,
            "parks_avg": 2,
            "transport_score": 0.6,
            "ecology_score": 6.0,
            "noise_level": 5.0,
        }

        # Get district data if available
        if city in cls.DISTRICT_INFRASTRUCTURE:
            if district and district in cls.DISTRICT_INFRASTRUCTURE[city]:
                default_features = cls.DISTRICT_INFRASTRUCTURE[city][district]

        # Calculate metro distance estimate (km)
        metro_distance = None
        if latitude and longitude:
            # Simplified: estimate based on city center
            city_centers = {
                "Москва": (55.7558, 37.6173),
                "Санкт-Петербург": (59.9343, 30.3351),
            }
            if city in city_centers:
                center_lat, center_lon = city_centers[city]
                # Rough distance calculation
                lat_diff = abs(latitude - center_lat)
                lon_diff = abs(longitude - center_lon)
                metro_distance = math.sqrt(lat_diff**2 + lon_diff**2) * 111  # km

        return {
            "metro_distance": metro_distance,
            "schools_count": default_features["schools_avg"],
            "shops_count": default_features["shops_avg"],
            "parks_count": default_features["parks_avg"],
            "transport_accessibility": default_features["transport_score"],
            "ecology_score": default_features["ecology_score"],
            "noise_level": default_features["noise_level"],
        }

    @classmethod
    def extract_building_features(
        cls,
        building_year: Optional[int] = None,
        renovation_year: Optional[int] = None,
        floor: Optional[int] = None,
        total_floors: Optional[int] = None,
        has_balcony: bool = False,
        has_parking: bool = False,
    ) -> Dict[str, Any]:
        """
        Извлечь признаки здания.

        Args:
            building_year: Year building was constructed
            renovation_year: Year of last renovation
            floor: Apartment floor
            total_floors: Total floors in building
            has_balcony: Has balcony or loggia
            has_parking: Has parking space
        """
        current_year = datetime.now().year

        # Building age
        building_age = None
        if building_year:
            building_age = current_year - building_year

        # Elevator presence (typically in buildings > 5 floors)
        has_elevator = total_floors is not None and total_floors > 5

        # Building class estimate
        building_class = "economy"
        if building_year and building_year >= 2010:
            building_class = "modern"
        elif building_year and building_year >= 1970:
            building_class = "standard"

        return {
            "building_age": building_age,
            "renovation_year": renovation_year,
            "has_balcony": has_balcony,
            "has_parking": has_parking,
            "has_elevator": has_elevator,
            "building_class": building_class,
        }

    @classmethod
    def extract_market_features(
        cls,
        city: str,
        district: Optional[str] = None,
        historical_prices: Optional[List[float]] = None,
        days: int = 60,
    ) -> Dict[str, Any]:
        """
        Извлечь рыночные признаки.

        Args:
            city: City name
            district: District name
            historical_prices: List of historical prices
            days: Number of days to analyze
        """
        # Default market indicators
        market_trend = 0.0  # Stable
        supply_demand_ratio = 1.0  # Balanced

        # Analyze price trend if data available
        if historical_prices and len(historical_prices) >= 10:
            # Simple trend: compare recent vs older prices
            mid_point = len(historical_prices) // 2
            older_avg = sum(historical_prices[:mid_point]) / mid_point
            recent_avg = sum(historical_prices[mid_point:]) / (len(historical_prices) - mid_point)

            if older_avg > 0:
                trend = (recent_avg - older_avg) / older_avg
                market_trend = max(-1, min(1, trend))  # Clamp to [-1, 1]

        # Neighborhood average price
        neighborhood_avg = 0
        if historical_prices:
            neighborhood_avg = sum(historical_prices) / len(historical_prices)

        return {
            "market_trend": market_trend,
            "supply_demand_ratio": supply_demand_ratio,
            "neighborhood_avg_price": neighborhood_avg,
        }

    @classmethod
    def extract_all_features(
        cls,
        city: str,
        district: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        building_year: Optional[int] = None,
        renovation_year: Optional[int] = None,
        floor: Optional[int] = None,
        total_floors: Optional[int] = None,
        has_balcony: bool = False,
        has_parking: bool = False,
        historical_prices: Optional[List[float]] = None,
        date: Optional[datetime] = None,
    ) -> EnhancedFeatures:
        """
        Extract all enhanced features.

        Combines temporal, location, building, and market features.
        """
        # Temporal features
        temporal = cls.extract_temporal_features(date)

        # Location features
        location = cls.extract_location_features(
            city, district, latitude, longitude
        )

        # Building features
        building = cls.extract_building_features(
            building_year, renovation_year, floor, total_floors,
            has_balcony, has_parking
        )

        # Market features
        market = cls.extract_market_features(
            city, district, historical_prices
        )

        return EnhancedFeatures(
            month=temporal["month"],
            day_of_week=temporal["day_of_week"],
            is_weekend=temporal["is_weekend"],
            is_holiday_season=temporal["is_holiday_season"],
            quarter=temporal["quarter"],
            metro_distance=location["metro_distance"],
            schools_count=location["schools_count"],
            shops_count=location["shops_count"],
            parks_count=location["parks_count"],
            transport_accessibility=location["transport_accessibility"],
            market_trend=market["market_trend"],
            supply_demand_ratio=market["supply_demand_ratio"],
            neighborhood_avg_price=market["neighborhood_avg_price"],
            building_age=building["building_age"],
            renovation_year=building["renovation_year"],
            has_balcony=building["has_balcony"],
            has_parking=building["has_parking"],
            has_elevator=building["has_elevator"],
            ecology_score=location["ecology_score"],
            noise_level=location["noise_level"],
        )


def get_enhanced_feature_names() -> List[str]:
    """
    Get list of enhanced feature names for ML model.

    Returns:
        List of feature names
    """
    return [
        # Temporal
        "month",
        "day_of_week",
        "is_weekend",
        "is_holiday_season",
        "quarter",
        "seasonal_factor",

        # Location
        "metro_distance",
        "schools_count",
        "shops_count",
        "parks_count",
        "transport_accessibility",
        "ecology_score",
        "noise_level",

        # Building
        "building_age",
        "renovation_year",
        "has_balcony",
        "has_parking",
        "has_elevator",

        # Market
        "market_trend",
        "supply_demand_ratio",
        "neighborhood_avg_price",
    ]
