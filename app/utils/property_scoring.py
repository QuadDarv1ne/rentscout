"""Property scoring and ranking system."""
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.models.schemas import PropertyCreate


@dataclass
class PropertyScore:
    """Property score components."""
    total: float
    price_score: float
    area_score: float
    location_score: float
    amenities_score: float
    verification_score: float
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "total": round(self.total, 2),
            "price_score": round(self.price_score, 2),
            "area_score": round(self.area_score, 2),
            "location_score": round(self.location_score, 2),
            "amenities_score": round(self.amenities_score, 2),
            "verification_score": round(self.verification_score, 2)
        }


class PropertyScoringSystem:
    """System for scoring and ranking properties."""
    
    # Weights for different scoring components
    WEIGHTS = {
        "price": 0.30,
        "area": 0.25,
        "location": 0.20,
        "amenities": 0.15,
        "verification": 0.10
    }
    
    @staticmethod
    def calculate_score(
        prop: PropertyCreate,
        market_avg_price: Optional[float] = None,
        market_avg_area: Optional[float] = None
    ) -> PropertyScore:
        """Calculate overall property score."""
        # Price score (lower price = higher score)
        price_score = PropertyScoringSystem._calculate_price_score(
            prop.price,
            market_avg_price
        )
        
        # Area score (larger area = higher score, considering price)
        area_score = PropertyScoringSystem._calculate_area_score(
            prop.area,
            market_avg_area
        )
        
        # Location score (based on district quality)
        location_score = PropertyScoringSystem._calculate_location_score(prop)
        
        # Amenities score (photos, description, features)
        amenities_score = PropertyScoringSystem._calculate_amenities_score(prop)
        
        # Verification score
        verification_score = 100.0 if prop.is_verified else 50.0
        
        # Calculate weighted total
        total = (
            price_score * PropertyScoringSystem.WEIGHTS["price"] +
            area_score * PropertyScoringSystem.WEIGHTS["area"] +
            location_score * PropertyScoringSystem.WEIGHTS["location"] +
            amenities_score * PropertyScoringSystem.WEIGHTS["amenities"] +
            verification_score * PropertyScoringSystem.WEIGHTS["verification"]
        )
        
        return PropertyScore(
            total=total,
            price_score=price_score,
            area_score=area_score,
            location_score=location_score,
            amenities_score=amenities_score,
            verification_score=verification_score
        )
    
    @staticmethod
    def _calculate_price_score(
        price: float,
        market_avg: Optional[float] = None
    ) -> float:
        """Calculate price score (0-100)."""
        if market_avg is None:
            # Without market data, use simple heuristic
            # Assume 50k is average, scale from there
            market_avg = 50000.0
        
        if price <= 0:
            return 0.0
        
        # Price 20% below average = 100 points
        # Price at average = 70 points
        # Price 50% above average = 40 points
        ratio = price / market_avg
        
        if ratio <= 0.8:
            return 100.0
        elif ratio <= 1.0:
            # Linear from 100 to 70
            return 100.0 - (ratio - 0.8) * 150
        elif ratio <= 1.5:
            # Linear from 70 to 40
            return 70.0 - (ratio - 1.0) * 60
        else:
            # Very expensive
            return max(0.0, 40.0 - (ratio - 1.5) * 20)
    
    @staticmethod
    def _calculate_area_score(
        area: Optional[float],
        market_avg: Optional[float] = None
    ) -> float:
        """Calculate area score (0-100)."""
        if area is None or area <= 0:
            return 50.0  # Neutral score when no data
        
        if market_avg is None:
            market_avg = 50.0  # Assume 50m² average
        
        # Larger than average = higher score
        ratio = area / market_avg
        
        if ratio >= 1.5:
            return 100.0
        elif ratio >= 1.0:
            # Linear from 70 to 100
            return 70.0 + (ratio - 1.0) * 60
        elif ratio >= 0.7:
            # Linear from 50 to 70
            return 50.0 + (ratio - 0.7) * 66.7
        else:
            # Small area
            return max(0.0, 50.0 - (0.7 - ratio) * 100)
    
    @staticmethod
    def _calculate_location_score(prop: PropertyCreate) -> float:
        """Calculate location score based on district (0-100)."""
        # Premium districts
        premium_districts = {
            "центр", "центральный", "цао", "downtown", "center",
            "патриаршие пруды", "чистые пруды", "арбат"
        }
        
        # Good districts
        good_districts = {
            "юго-запад", "юго-западный", "северо-запад",
            "хамовники", "тверской", "пресненский"
        }
        
        # Check city (some cities are premium)
        city_lower = (prop.city or "").lower()
        district_lower = (prop.district or "").lower()
        
        # Moscow center = highest score
        if "москва" in city_lower or "moscow" in city_lower:
            if any(d in district_lower for d in premium_districts):
                return 95.0
            elif any(d in district_lower for d in good_districts):
                return 80.0
            else:
                return 65.0
        
        # Saint Petersburg
        if "санкт-петербург" in city_lower or "петербург" in city_lower:
            if any(d in district_lower for d in premium_districts):
                return 90.0
            elif "невский" in district_lower:
                return 85.0
            else:
                return 70.0
        
        # Other major cities
        major_cities = ["казань", "екатеринбург", "новосибирск", "нижний новгород"]
        if any(city in city_lower for city in major_cities):
            return 75.0
        
        # Default score
        return 60.0
    
    @staticmethod
    def _calculate_amenities_score(prop: PropertyCreate) -> float:
        """Calculate amenities score based on available information (0-100)."""
        score = 0.0
        
        # Photos
        if prop.photos and len(prop.photos) > 0:
            # More photos = better
            score += min(30.0, len(prop.photos) * 5)
        
        # Description
        if prop.description and len(prop.description) > 50:
            score += 25.0
        elif prop.description:
            score += 15.0
        
        # Features
        if prop.features:
            feature_count = len(prop.features) if isinstance(prop.features, dict) else 0
            score += min(25.0, feature_count * 5)
        
        # Contact information
        if prop.contact_phone:
            score += 10.0
        if prop.contact_name:
            score += 10.0
        
        return min(100.0, score)
    
    @staticmethod
    def rank_properties(
        properties: list[PropertyCreate],
        market_stats: Optional[Dict[str, float]] = None
    ) -> list[tuple[PropertyCreate, PropertyScore]]:
        """Rank properties by score."""
        if market_stats is None:
            # Calculate market stats from properties
            prices = [p.price for p in properties if p.price > 0]
            areas = [p.area for p in properties if p.area and p.area > 0]
            
            market_stats = {
                "avg_price": sum(prices) / len(prices) if prices else None,
                "avg_area": sum(areas) / len(areas) if areas else None
            }
        
        # Calculate scores
        scored_properties = [
            (
                prop,
                PropertyScoringSystem.calculate_score(
                    prop,
                    market_stats.get("avg_price"),
                    market_stats.get("avg_area")
                )
            )
            for prop in properties
        ]
        
        # Sort by total score descending
        scored_properties.sort(key=lambda x: x[1].total, reverse=True)
        
        return scored_properties
    
    @staticmethod
    def get_value_rating(score: PropertyScore) -> str:
        """Get value rating based on score."""
        if score.total >= 85:
            return "Отличное"
        elif score.total >= 70:
            return "Хорошее"
        elif score.total >= 55:
            return "Среднее"
        elif score.total >= 40:
            return "Ниже среднего"
        else:
            return "Плохое"
