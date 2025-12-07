from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional

from app.dependencies.parsers import get_parsers
from app.models.schemas import Property, PropertyCreate
from app.services.cache import cache
from app.services.filter import PropertyFilter
from app.services.search import SearchService
from app.utils.logger import logger
from app.utils.retry import retry
from app.utils.parser_errors import (
    ErrorClassifier,
    ErrorSeverity,
    ErrorRetryability,
    AuthenticationError,
)

router = APIRouter()


@retry(max_attempts=3, initial_delay=1.0, exceptions=(Exception,))
async def _search_properties(city: str, property_type: str) -> List[PropertyCreate]:
    """Вспомогательная функция поиска с поддержкой повторных попыток."""
    search_service = SearchService()
    return await search_service.search(city, property_type)


@router.get(
    "/properties",
    response_model=list[Property],
    summary="Онлайн-поиск объявлений через парсеры",
    response_description="Список объявлений после фильтрации",
)
@router.get(
    "/properties/search",
    response_model=list[Property],
    summary="Онлайн-поиск объявлений (алиас /properties)",
    response_description="Список объявлений после фильтрации",
)
@cache(expire=300)
async def get_properties(
    city: str = Query(..., min_length=2),
    property_type: str = Query("Квартира"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_rooms: Optional[int] = Query(None, ge=0),
    max_rooms: Optional[int] = Query(None, ge=0),
    min_area: Optional[float] = Query(None, ge=0),
    max_area: Optional[float] = Query(None, ge=0),
    district: Optional[str] = Query(None, description="Фильтр по району города"),
    has_photos: Optional[bool] = Query(None, description="Фильтр по наличию фотографий"),
    source: Optional[str] = Query(None, description="Фильтр по источнику (avito, cian и т.д.)"),
    max_price_per_sqm: Optional[float] = Query(None, ge=0, description="Максимальная цена за квадратный метр"),
    parsers: list = Depends(get_parsers),
) -> List[Property]:
    """
    Получить список свойств с поддержкой фильтрации.

    Args:
        city: Название города для поиска
        property_type: Тип недвижимости
        min_price: Минимальная цена
        max_price: Максимальная цена
        min_rooms: Минимальное количество комнат
        max_rooms: Максимальное количество комнат
        min_area: Минимальная площадь
        max_area: Максимальная площадь
        district: Район
        has_photos: Наличие фотографий
        source: Источник
        max_price_per_sqm: Максимальная цена за кв.м
        parsers: Зависимость парсеров

    Returns:
        Список свойств, отфильтрованных по заданным критериям

    Raises:
        HTTPException: Если поиск не удался после всех повторных попыток
    """
    try:
        # Используем вспомогательную функцию с retry логикой
        all_properties = await _search_properties(city, property_type)

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
            max_price_per_sqm=max_price_per_sqm,
        )

        filtered_properties = property_filter.filter(all_properties)

        logger.info(
            f"Search completed for {city}: "
            f"found {len(all_properties)} properties, "
            f"after filtering: {len(filtered_properties)}"
        )

        return filtered_properties

    except Exception as e:
        # Классифицируем ошибку для умной обработки
        classification = ErrorClassifier.classify(e)
        
        # Логируем с учетом серьезности
        if classification["severity"] == ErrorSeverity.CRITICAL:
            logger.critical(f"Critical API Error: {classification['type']}: {str(e)}", exc_info=True)
            
            # AuthenticationError требует немедленного внимания
            if isinstance(e, AuthenticationError):
                raise HTTPException(
                    status_code=401,
                    detail="Authentication failed. Please check API credentials.",
                )
            
            raise HTTPException(
                status_code=500,
                detail="Internal Server Error.",
            )
        else:
            logger.warning(f"API Error during property search ({classification['type']}): {str(e)}")
            
            # Для временных ошибок возвращаем 503 Service Unavailable
            if classification["retryability"] != ErrorRetryability.NO_RETRY:
                raise HTTPException(
                    status_code=503,
                    detail="Service temporarily unavailable. Please try again later.",
                )
            
            # Для постоянных ошибок (парсинг) возвращаем 400 Bad Request
            raise HTTPException(
                status_code=400,
                detail="Invalid search parameters or data format.",
            )