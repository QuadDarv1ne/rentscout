from fastapi import APIRouter, Depends, Query, HTTPException
from app.dependencies.parsers import get_parsers
from app.models.schemas import Property, PropertyCreate
from app.services.filter import PropertyFilter
from app.services.cache import cache
from app.utils.logger import logger

router = APIRouter()

@router.get("/properties", response_model=list[Property])
@cache(expire=300)
async def get_properties(
    city: str = Query(..., min_length=2),
    property_type: str = Query("Квартира"),
    min_price: float = Query(None, ge=0),
    max_price: float = Query(None, ge=0),
    min_rooms: int = Query(None, ge=0),
    max_rooms: int = Query(None, ge=0),
    min_area: float = Query(None, ge=0),
    max_area: float = Query(None, ge=0),
    district: str = Query(None, description="Фильтр по району города"),
    has_photos: bool = Query(None, description="Фильтр по наличию фотографий"),
    source: str = Query(None, description="Фильтр по источнику (avito, cian и т.д.)"),
    max_price_per_sqm: float = Query(None, ge=0, description="Максимальная цена за квадратный метр"),
    parsers: list = Depends(get_parsers)
):
    try:
        all_properties = []
        for parser in parsers:
            try:
                data = await parser.parse(city, {"type": property_type})
                all_properties.extend(data)
            except Exception as e:
                logger.error(f"Parser {parser.__class__.__name__} failed: {str(e)}")
        
        # Apply filters
        property_filter = PropertyFilter(
            min_price=min_price,
            max_price=max_price,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            min_area=min_area,
            max_area=max_area,
            property_type=property_type,
            district=district,
            has_photos=has_photos,
            source=source,
            max_price_per_sqm=max_price_per_sqm
        )
        
        filtered_properties = property_filter.filter(all_properties)
        
        # Convert PropertyCreate objects to Property objects
        result_properties = []
        for prop in filtered_properties:
            # Generate a simple ID based on source and external_id
            prop_id = f"{prop.source}_{prop.external_id}"
            property_obj = Property(
                id=prop_id,
                source=prop.source,
                external_id=prop.external_id,
                title=prop.title,
                price=prop.price,
                rooms=prop.rooms,
                area=prop.area,
                location=prop.location,
                photos=prop.photos
            )
            result_properties.append(property_obj)
        
        return result_properties
    
    except Exception as e:
        logger.critical(f"API Error: {str(e)}")
        raise HTTPException(500, "Internal Server Error")