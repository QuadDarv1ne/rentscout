"""Property scoring and ranking system."""
from typing import Dict, Any, Optional, List
import math
from datetime import datetime, timedelta
from dataclasses import dataclass

from app.models.schemas import Property


@dataclass
class PropertyScore:
    """Property score components."""
    total: float
    price_score: float
    area_score: float
    location_score: float
    amenities_score: float
    verification_score: float
    freshness_score: float  # New score component for recency
    photos_score: float     # New score component for photo quality
    price_per_sqm_score: float  # New score for price per square meter efficiency
    market_position_score: float  # New score for market position
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "total": round(self.total, 2),
            "price_score": round(self.price_score, 2),
            "area_score": round(self.area_score, 2),
            "location_score": round(self.location_score, 2),
            "amenities_score": round(self.amenities_score, 2),
            "verification_score": round(self.verification_score, 2),
            "freshness_score": round(self.freshness_score, 2),
            "photos_score": round(self.photos_score, 2),
            "price_per_sqm_score": round(self.price_per_sqm_score, 2),
            "market_position_score": round(self.market_position_score, 2)
        }


class PropertyScoringSystem:
    """System for scoring and ranking properties."""
    
    # Weights for different scoring components
    WEIGHTS = {
        "price": 0.20,
        "area": 0.15,
        "location": 0.15,
        "amenities": 0.10,
        "verification": 0.05,
        "freshness": 0.10,
        "photos": 0.05,
        "price_per_sqm": 0.10,  # New weight
        "market_position": 0.10,  # New weight
    }
    
    @staticmethod
    def calculate_score(
        prop: Property,
        market_avg_price: Optional[float] = None,
        market_avg_area: Optional[float] = None,
        market_avg_price_per_sqm: Optional[float] = None,
        all_properties: Optional[List[Property]] = None
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
        
        # Freshness score (newer listings = higher score)
        freshness_score = PropertyScoringSystem._calculate_freshness_score(prop)
        
        # Photos score (more/better photos = higher score)
        photos_score = PropertyScoringSystem._calculate_photos_score(prop)
        
        # Price per square meter score
        price_per_sqm_score = PropertyScoringSystem._calculate_price_per_sqm_score(
            prop.price,
            prop.area,
            market_avg_price_per_sqm
        )
        
        # Market position score (how this property compares to others)
        market_position_score = PropertyScoringSystem._calculate_market_position_score(
            prop,
            all_properties
        )
        
        # Calculate weighted total
        total = (
            price_score * PropertyScoringSystem.WEIGHTS["price"] +
            area_score * PropertyScoringSystem.WEIGHTS["area"] +
            location_score * PropertyScoringSystem.WEIGHTS["location"] +
            amenities_score * PropertyScoringSystem.WEIGHTS["amenities"] +
            verification_score * PropertyScoringSystem.WEIGHTS["verification"] +
            freshness_score * PropertyScoringSystem.WEIGHTS["freshness"] +
            photos_score * PropertyScoringSystem.WEIGHTS["photos"] +
            price_per_sqm_score * PropertyScoringSystem.WEIGHTS["price_per_sqm"] +
            market_position_score * PropertyScoringSystem.WEIGHTS["market_position"]
        )
        
        return PropertyScore(
            total=total,
            price_score=price_score,
            area_score=area_score,
            location_score=location_score,
            amenities_score=amenities_score,
            verification_score=verification_score,
            freshness_score=freshness_score,
            photos_score=photos_score,
            price_per_sqm_score=price_per_sqm_score,
            market_position_score=market_position_score
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
    def _calculate_location_score(prop: Property) -> float:
        """Calculate location score based on district (0-100)."""
        # Premium districts
        premium_districts = {
            "центр", "центральный", "цао", "downtown", "center",
            "патриаршие пруды", "чистые пруды", "арбат",
            "таганский", "мякинино", "покровское-стрешнево"
        }
        
        # Good districts
        good_districts = {
            "юго-запад", "юго-западный", "северо-запад",
            "хамовники", "тверской", "пресненский",
            "басманный", "якиманка", "зamosкворечье"
        }
        
        # Emerging districts (potential growth)
        emerging_districts = {
            "зеленоград", "новое переделкино", "солнцево",
            "троицк", "щербинка", "люберцы"
        }
        
        # Check city (some cities are premium)
        city_lower = (prop.city or "").lower()
        district_lower = (prop.district or "").lower()
        
        # Moscow center = highest score
        if "москва" in city_lower or "moscow" in city_lower:
            if any(d in district_lower for d in premium_districts):
                return 95.0
            elif any(d in district_lower for d in good_districts):
                return 85.0
            elif any(d in district_lower for d in emerging_districts):
                return 75.0  # Emerging areas with potential
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
    def _calculate_amenities_score(prop: Property) -> float:
        """Calculate amenities score based on available information (0-100)."""
        score = 0.0
        
        # Photos
        if prop.photos and len(prop.photos) > 0:
            # More photos = better
            score += min(20.0, len(prop.photos) * 3)
        
        # Description
        if prop.description and len(prop.description) > 50:
            score += 15.0
        elif prop.description:
            score += 10.0
        
        # Features
        if prop.features:
            feature_count = len(prop.features) if isinstance(prop.features, dict) else 0
            score += min(20.0, feature_count * 4)
        
        # Contact information
        if prop.contact_phone:
            score += 10.0
        if prop.contact_name:
            score += 10.0
            
        # Address completeness
        if prop.address and len(prop.address) > 10:
            score += 10.0
        
        # Floor information
        if prop.floor and prop.total_floors:
            score += 5.0
        
        return min(100.0, score)
    
    @staticmethod
    def _calculate_freshness_score(prop: Property) -> float:
        """Calculate freshness score based on when the property was listed (0-100)."""
        # If we don't have a created_at timestamp, return neutral score
        if not hasattr(prop, 'created_at') or prop.created_at is None:
            return 75.0  # Neutral score
        
        # Calculate days since listing
        if isinstance(prop.created_at, str):
            try:
                listing_date = datetime.fromisoformat(prop.created_at.replace('Z', '+00:00'))
            except ValueError:
                return 75.0  # Neutral score if parsing fails
        else:
            listing_date = prop.created_at
        
        days_since_listing = (datetime.now().replace(tzinfo=listing_date.tzinfo) - listing_date).days
        
        # Newer listings get higher scores
        if days_since_listing <= 1:
            return 100.0  # Today
        elif days_since_listing <= 3:
            return 90.0   # Within 3 days
        elif days_since_listing <= 7:
            return 80.0   # Within a week
        elif days_since_listing <= 14:
            return 70.0   # Within 2 weeks
        elif days_since_listing <= 30:
            return 60.0   # Within a month
        else:
            return max(20.0, 50.0 - (days_since_listing - 30) * 0.5)  # Older listings
    
    @staticmethod
    def _calculate_photos_score(prop: Property) -> float:
        """Calculate photos score based on quantity and quality (0-100)."""
        if not prop.photos or len(prop.photos) == 0:
            return 0.0
        
        photo_count = len(prop.photos)
        
        # Quantity score (0-50)
        quantity_score = min(50.0, photo_count * 10)
        
        # Quality heuristics (0-50)
        quality_score = 0.0
        
        # Check for diverse photos (interior, exterior, kitchen, bathroom, etc.)
        # This is a simplified check - in reality, you'd want image analysis
        if photo_count >= 5:
            quality_score += 20.0  # Enough photos for variety
        elif photo_count >= 3:
            quality_score += 10.0
        
        # Bonus for having many photos
        if photo_count >= 10:
            quality_score += 15.0
        elif photo_count >= 7:
            quality_score += 10.0
        
        total_photos_score = quantity_score + quality_score
        return min(100.0, total_photos_score)
    
    @staticmethod
    def _calculate_price_per_sqm_score(
        price: float,
        area: Optional[float],
        market_avg_price_per_sqm: Optional[float] = None
    ) -> float:
        """Calculate price per square meter efficiency score (0-100)."""
        if area is None or area <= 0 or price <= 0:
            return 50.0  # Neutral score when no data
        
        price_per_sqm = price / area
        
        if market_avg_price_per_sqm is None:
            # Default assumption: 1000 RUB per sqm is average
            market_avg_price_per_sqm = 1000.0
        
        # Lower price per sqm = higher score
        ratio = price_per_sqm / market_avg_price_per_sqm
        
        if ratio <= 0.7:
            return 100.0  # Great value
        elif ratio <= 0.9:
            return 90.0   # Good value
        elif ratio <= 1.1:
            return 80.0   # Average value
        elif ratio <= 1.3:
            return 70.0   # Slightly overpriced
        elif ratio <= 1.5:
            return 60.0   # Overpriced
        else:
            return max(0.0, 50.0 - (ratio - 1.5) * 10)  # Significantly overpriced
    
    @staticmethod
    def _calculate_market_position_score(
        prop: Property,
        all_properties: Optional[List[Property]] = None
    ) -> float:
        """Calculate market position score based on how this property compares to others (0-100)."""
        if not all_properties or len(all_properties) < 2:
            return 75.0  # Neutral score when no comparison data
        
        # Filter properties in the same city
        city_props = [p for p in all_properties if p.city == prop.city]
        if len(city_props) < 2:
            return 75.0
        
        # Calculate percentiles for key metrics
        prices = sorted([p.price for p in city_props if p.price and p.price > 0])
        areas = sorted([p.area for p in city_props if p.area and p.area > 0])
        
        if not prices or not areas:
            return 75.0
        
        # Calculate percentiles
        price_percentile = PropertyScoringSystem._get_percentile(prices, prop.price or 0)
        area_percentile = PropertyScoringSystem._get_percentile(areas, prop.area or 0)
        
        # Market position score:
        # - High area percentile + low price percentile = great value
        # - Low area percentile + high price percentile = poor value
        
        # Normalize to 0-100 scale
        # Best value: high area, low price = 100
        # Worst value: low area, high price = 0
        market_score = ((area_percentile / 100.0) * 70.0) + ((100.0 - price_percentile) * 30.0)
        
        return min(100.0, max(0.0, market_score))
    
    @staticmethod
    def _get_percentile(sorted_list: List[float], value: float) -> float:
        """Calculate percentile of a value in a sorted list."""
        if not sorted_list or value <= 0:
            return 50.0  # Neutral percentile
        
        # Find position using binary search approach
        left, right = 0, len(sorted_list) - 1
        pos = 0
        
        while left <= right:
            mid = (left + right) // 2
            if sorted_list[mid] <= value:
                pos = mid
                left = mid + 1
            else:
                right = mid - 1
        
        percentile = (pos / (len(sorted_list) - 1)) * 100 if len(sorted_list) > 1 else 50.0
        return percentile
    
    @staticmethod
    def rank_properties(
        properties: List[Property],
        market_stats: Optional[Dict[str, float]] = None
    ) -> List[tuple[Property, PropertyScore]]:
        """Rank properties by score."""
        if market_stats is None:
            # Calculate market stats from properties
            prices = [p.price for p in properties if p.price > 0]
            areas = [p.area for p in properties if p.area and p.area > 0]
            
            # Calculate price per sqm
            prices_per_sqm = []
            for p in properties:
                if p.price and p.area and p.area > 0:
                    prices_per_sqm.append(p.price / p.area)
            
            market_stats = {
                "avg_price": sum(prices) / len(prices) if prices else None,
                "avg_area": sum(areas) / len(areas) if areas else None,
                "avg_price_per_sqm": sum(prices_per_sqm) / len(prices_per_sqm) if prices_per_sqm else None
            }
        
        # Calculate scores
        scored_properties = [
            (
                prop,
                PropertyScoringSystem.calculate_score(
                    prop,
                    market_stats.get("avg_price"),
                    market_stats.get("avg_area"),
                    market_stats.get("avg_price_per_sqm"),
                    properties  # Pass all properties for market position calculation
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