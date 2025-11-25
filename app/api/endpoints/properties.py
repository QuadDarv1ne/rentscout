from fastapi import APIRouter, Depends, Query, HTTPException
from app.dependencies.parsers import get_parsers
from app.models.schemas import Property
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
            property_type=property_type
        )
        
        return property_filter.filter(all_properties)
    
    except Exception as e:
        logger.critical(f"API Error: {str(e)}")
        raise HTTPException(500, "Internal Server Error")