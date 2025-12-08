"""Advanced search utilities with filtering and ranking."""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from app.models.schemas import PropertyCreate


class SortOrder(str, Enum):
    """Sorting order options."""
    ASC = "asc"
    DESC = "desc"


@dataclass
class SearchFilter:
    """Advanced search filter."""
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rooms: Optional[int] = None
    max_rooms: Optional[int] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    cities: Optional[List[str]] = None
    districts: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    min_floor: Optional[int] = None
    max_floor: Optional[int] = None
    has_photos: bool = False
    has_description: bool = False
    verified_only: bool = False
    
    def matches(self, prop: PropertyCreate) -> bool:
        """Check if property matches all filter criteria."""
        # Price filter
        if self.min_price is not None and prop.price < self.min_price:
            return False
        if self.max_price is not None and prop.price > self.max_price:
            return False
        
        # Rooms filter
        if prop.rooms is not None:
            if self.min_rooms is not None and prop.rooms < self.min_rooms:
                return False
            if self.max_rooms is not None and prop.rooms > self.max_rooms:
                return False
        
        # Area filter
        if prop.area is not None:
            if self.min_area is not None and prop.area < self.min_area:
                return False
            if self.max_area is not None and prop.area > self.max_area:
                return False
        
        # City filter
        if self.cities:
            prop_city = None
            if prop.city:
                prop_city = prop.city
            elif prop.location and isinstance(prop.location, dict):
                prop_city = prop.location.get("city")
            
            if not prop_city or prop_city not in self.cities:
                return False
        
        # District filter
        if self.districts:
            prop_district = None
            if prop.district:
                prop_district = prop.district
            elif prop.location and isinstance(prop.location, dict):
                prop_district = prop.location.get("district")
            
            if not prop_district or prop_district not in self.districts:
                return False
        
        # Source filter
        if self.sources and prop.source not in self.sources:
            return False
        
        # Floor filter
        if prop.floor is not None:
            if self.min_floor is not None and prop.floor < self.min_floor:
                return False
            if self.max_floor is not None and prop.floor > self.max_floor:
                return False
        
        # Photos filter
        if self.has_photos and (not prop.photos or len(prop.photos) == 0):
            return False
        
        # Description filter
        if self.has_description and (not prop.description or not prop.description.strip()):
            return False
        
        # Verification filter
        if self.verified_only and not prop.is_verified:
            return False
        
        return True


class AdvancedSearchEngine:
    """Advanced search engine with ranking and filtering."""
    
    @staticmethod
    def filter_properties(
        properties: List[PropertyCreate],
        filters: SearchFilter
    ) -> List[PropertyCreate]:
        """Filter properties based on criteria."""
        return [prop for prop in properties if filters.matches(prop)]
    
    @staticmethod
    def rank_properties(
        properties: List[PropertyCreate],
        sort_by: str = "price",
        order: SortOrder = SortOrder.ASC
    ) -> List[PropertyCreate]:
        """Sort properties by given criterion."""
        reverse = order == SortOrder.DESC
        
        if sort_by == "price":
            return sorted(properties, key=lambda p: p.price or 0, reverse=reverse)
        elif sort_by == "area":
            return sorted(properties, key=lambda p: p.area or 0, reverse=reverse)
        elif sort_by == "rooms":
            return sorted(properties, key=lambda p: p.rooms or 0, reverse=reverse)
        elif sort_by == "price_per_area":
            def get_price_per_area(p):
                if p.area and p.area > 0:
                    return p.price / p.area
                return float('inf')
            return sorted(properties, key=get_price_per_area, reverse=reverse)
        elif sort_by == "recent":
            # This would require timestamp data
            return properties
        else:
            return properties
    
    @staticmethod
    def deduplicate_properties(
        properties: List[PropertyCreate],
        match_threshold: float = 0.8
    ) -> List[PropertyCreate]:
        """Remove duplicate properties based on similarity."""
        if not properties:
            return []
        
        unique = []
        for prop in properties:
            is_duplicate = False
            
            for existing in unique:
                if AdvancedSearchEngine._is_duplicate(prop, existing, match_threshold):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(prop)
        
        return unique
    
    @staticmethod
    def _is_duplicate(prop1: PropertyCreate, prop2: PropertyCreate, threshold: float) -> bool:
        """Check if two properties are duplicates."""
        # Same source and external_id = definitely duplicate
        if prop1.source == prop2.source and prop1.external_id == prop2.external_id:
            return True
        
        # Calculate similarity score
        score = 0
        max_score = 0
        
        # Price similarity (within 5% is suspicious)
        max_score += 1
        if prop1.price and prop2.price:
            price_diff = abs(prop1.price - prop2.price) / max(prop1.price, prop2.price)
            if price_diff < 0.05:
                score += 1
        
        # Title similarity (Levenshtein distance)
        max_score += 1
        if prop1.title and prop2.title:
            similarity = AdvancedSearchEngine._string_similarity(
                prop1.title, prop2.title
            )
            if similarity > 0.8:
                score += 1
        
        # Area similarity (within 10%)
        max_score += 1
        if prop1.area and prop2.area:
            area_diff = abs(prop1.area - prop2.area) / max(prop1.area, prop2.area)
            if area_diff < 0.1:
                score += 1
        
        # Rooms similarity
        max_score += 1
        if prop1.rooms and prop2.rooms and prop1.rooms == prop2.rooms:
            score += 1
        
        # Location similarity
        max_score += 1
        if prop1.city and prop2.city and prop1.city == prop2.city:
            score += 1
        
        return score / max_score >= threshold
    
    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """Calculate string similarity using simple character overlap."""
        # Normalize strings
        s1 = re.sub(r'\s+', ' ', s1.lower()).strip()
        s2 = re.sub(r'\s+', ' ', s2.lower()).strip()
        
        if s1 == s2:
            return 1.0
        
        # Extract important words (ignore common words)
        common_words = {'и', 'в', 'на', 'с', 'из', 'для', 'к', 'от', 'до', 'по'}
        words1 = set(w for w in s1.split() if w not in common_words and len(w) > 2)
        words2 = set(w for w in s2.split() if w not in common_words and len(w) > 2)
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    @staticmethod
    def get_price_distribution(
        properties: List[PropertyCreate],
        bucket_count: int = 10
    ) -> Dict[str, Any]:
        """Get price distribution statistics."""
        if not properties:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "median": None,
                "distribution": []
            }
        
        prices = sorted([p.price for p in properties if p.price])
        
        if not prices:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "median": None,
                "distribution": []
            }
        
        min_price = prices[0]
        max_price = prices[-1]
        avg_price = sum(prices) / len(prices)
        
        # Calculate median
        if len(prices) % 2 == 0:
            median = (prices[len(prices) // 2 - 1] + prices[len(prices) // 2]) / 2
        else:
            median = prices[len(prices) // 2]
        
        # Create price buckets
        bucket_size = (max_price - min_price) / bucket_count if max_price > min_price else 1
        distribution = [0] * bucket_count
        
        for price in prices:
            bucket_idx = min(int((price - min_price) / bucket_size), bucket_count - 1)
            distribution[bucket_idx] += 1
        
        return {
            "count": len(prices),
            "min": min_price,
            "max": max_price,
            "avg": avg_price,
            "median": median,
            "distribution": distribution
        }
