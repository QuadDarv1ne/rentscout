from app.models.schemas import Property
from typing import List, Optional


class PropertyFilter:
    def __init__(
        self,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rooms: Optional[int] = None,
        max_rooms: Optional[int] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        property_type: Optional[str] = None
    ):
        self.min_price = min_price
        self.max_price = max_price
        self.min_rooms = min_rooms
        self.max_rooms = max_rooms
        self.min_area = min_area
        self.max_area = max_area
        self.property_type = property_type

    def filter(self, properties: List[Property]) -> List[Property]:
        filtered = []
        for prop in properties:
            # Skip properties with invalid prices
            if prop.price <= 0:
                continue
                
            # Price filtering
            if self.min_price is not None and prop.price < self.min_price:
                continue
            if self.max_price is not None and prop.price > self.max_price:
                continue
                
            # Room filtering
            if self.min_rooms is not None and (prop.rooms is None or prop.rooms < self.min_rooms):
                continue
            if self.max_rooms is not None and (prop.rooms is None or prop.rooms > self.max_rooms):
                continue
                
            # Area filtering
            if self.min_area is not None and (prop.area is None or prop.area < self.min_area):
                continue
            if self.max_area is not None and (prop.area is None or prop.area > self.max_area):
                continue
                
            # Property type filtering (based on title)
            if self.property_type is not None and self.property_type.lower() not in prop.title.lower():
                continue
                
            filtered.append(prop)
        
        # Sort by price ascending and limit to 1000 results
        return sorted(filtered, key=lambda x: x.price)[:1000]