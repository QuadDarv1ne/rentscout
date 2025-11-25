from pydantic import BaseModel, ConfigDict
from typing import Optional

class PropertyBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    source: str
    external_id: str
    title: str
    price: float
    rooms: Optional[int] = None
    area: Optional[float] = None
    location: Optional[dict] = None
    photos: list[str] = []

class PropertyCreate(PropertyBase):
    pass

class Property(PropertyBase):
    id: str
    
    model_config = ConfigDict(from_attributes=True)
