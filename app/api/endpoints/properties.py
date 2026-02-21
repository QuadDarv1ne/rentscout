from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import StreamingResponse
from typing import List, Optional
import io
import time

from app.dependencies.parsers import get_parsers
from app.models.schemas import Property, PropertyCreate, PaginatedProperties
from app.services.advanced_cache import cached
from app.services.filter import PropertyFilter
from app.services.search import SearchService
from app.services.optimized_search import OptimizedSearchService
from app.services.export import ExportService
from app.utils.logger import logger
from app.utils.retry import retry
from app.utils.metrics import metrics_collector
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
    search_service = OptimizedSearchService()
    results, is_cached, stats = await search_service.search_cached(city, property_type)
    return results


@router.get(
    "/properties",
    response_model=PaginatedProperties,
    summary="Онлайн-поиск объявлений через парсеры",
    response_description="Пагинированный список объявлений после фильтрации",
)
@router.get(
    "/properties/search",
    response_model=PaginatedProperties,
    summary="Онлайн-поиск объявлений (алиас /properties)",
    response_description="Пагинированный список объявлений после фильтрации",
)
@cached(expire=300, prefix="properties_search")
async def get_properties(
    city: str = Query(..., min_length=2),
    property_type: str = Query("Квартира"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_rooms: Optional[int] = Query(None, ge=0),
    max_rooms: Optional[int] = Query(None, ge=0),
    min_area: Optional[float] = Query(None, ge=0),
    max_area: Optional[float] = Query(None, ge=0),
    min_floor: Optional[int] = Query(None, ge=0),
    max_floor: Optional[int] = Query(None, ge=0),
    min_total_floors: Optional[int] = Query(None, ge=0),
    max_total_floors: Optional[int] = Query(None, ge=0),
    district: Optional[str] = Query(None, description="Фильтр по району города"),
    has_photos: Optional[bool] = Query(None, description="Фильтр по наличию фотографий"),
    source: Optional[str] = Query(None, description="Фильтр по источнику (avito, cian и т.д.)"),
    features: Optional[List[str]] = Query(None, description="Список обязательных характеристик"),
    max_price_per_sqm: Optional[float] = Query(None, ge=0, description="Максимальная цена за квадратный метр"),
    has_contact: Optional[bool] = Query(None, description="Фильтр по наличию контактной информации"),
    min_first_seen: Optional[str] = Query(None, description="Минимальная дата первого появления (ISO format)"),
    max_first_seen: Optional[str] = Query(None, description="Максимальная дата первого появления (ISO format)"),
    min_last_seen: Optional[str] = Query(None, description="Минимальная дата последнего появления (ISO format)"),
    max_last_seen: Optional[str] = Query(None, description="Максимальная дата последнего появления (ISO format)"),
    sort_by: str = Query("price", pattern="^(price|area|rooms|floor|first_seen|last_seen)$", description="Поле для сортировки (price, area, rooms, floor, first_seen, last_seen)"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Порядок сортировки (asc или desc)"),
    skip: int = Query(0, ge=0, description="Количество записей для пропуска"),
    limit: int = Query(50, ge=1, le=100, description="Максимальное количество записей в ответе (1-100)"),
    parsers: list = Depends(get_parsers),
) -> PaginatedProperties:
    """
    Получить список свойств с поддержкой фильтрации и пагинации.

    Args:
        city: Название города для поиска
        property_type: Тип недвижимости
        min_price: Минимальная цена
        max_price: Максимальная цена
        min_rooms: Минимальное количество комнат
        max_rooms: Максимальное количество комнат
        min_area: Минимальная площадь
        max_area: Максимальная площадь
        min_floor: Минимальный этаж
        max_floor: Максимальный этаж
        min_total_floors: Минимальное количество этажей в здании
        max_total_floors: Максимальное количество этажей в здании
        district: Район
        has_photos: Наличие фотографий
        source: Источник
        features: Список обязательных характеристик
        max_price_per_sqm: Максимальная цена за кв.м
        has_contact: Наличие контактной информации
        min_first_seen: Минимальная дата первого появления (ISO format)
        max_first_seen: Максимальная дата первого появления (ISO format)
        min_last_seen: Минимальная дата последнего появления (ISO format)
        max_last_seen: Максимальная дата последнего появления (ISO format)
        sort_by: Поле для сортировки (price, area, rooms, floor, first_seen, last_seen)
        sort_order: Порядок сортировки (asc или desc)
        skip: Количество записей для пропуска (пагинация)
        limit: Максимальное количество записей (1-100)
        parsers: Зависимость парсеров

    Returns:
        Пагинированный список свойств, отфильтрованных по заданным критериям

    Raises:
        HTTPException: Если поиск не удался после всех повторных попыток
    """
    try:
        # Используем вспомогательную функцию с retry логикой
        all_properties = await _search_properties(city, property_type)
        
        # Log cache statistics
        logger.info(f"Search for {city} completed. Properties found: {len(all_properties)}")

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
            min_floor=min_floor,
            max_floor=max_floor,
            min_total_floors=min_total_floors,
            max_total_floors=max_total_floors,
            features=features,
            has_contact=has_contact,
            min_first_seen=min_first_seen,
            max_first_seen=max_first_seen,
            min_last_seen=min_last_seen,
            max_last_seen=max_last_seen,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        filtered_properties, total_count = property_filter.filter(all_properties, skip=skip, limit=limit)

        # Вычисляем значения для пагинации
        page = (skip // limit) + 1
        pages = (total_count + limit - 1) // limit if total_count > 0 else 1
        has_next = (skip + limit) < total_count
        has_prev = skip > 0

        # Записываем метрики пагинации
        metrics_collector.record_pagination(page_size=limit, page_number=page)

        logger.info(
            f"Search completed for {city}: "
            f"found {len(all_properties)} properties, "
            f"after filtering: {total_count} total, "
            f"returned {len(filtered_properties)} (skip={skip}, limit={limit})"
        )

        return PaginatedProperties(
            items=filtered_properties,
            total=total_count,
            skip=skip,
            limit=limit,
            page=page,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev,
        )

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


@router.get(
    "/properties/export/{format}",
    summary="Экспортировать результаты поиска",
    response_description="Файл с результатами поиска",
    tags=["export"],
)
async def export_properties(
    format: str = Path(..., pattern="^(csv|json|jsonl)$", description="Формат экспорта (csv, json, jsonl)"),
    city: str = Query(..., min_length=2),
    property_type: str = Query("Квартира"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_rooms: Optional[int] = Query(None, ge=0),
    max_rooms: Optional[int] = Query(None, ge=0),
    min_area: Optional[float] = Query(None, ge=0),
    max_area: Optional[float] = Query(None, ge=0),
    district: Optional[str] = Query(None),
    has_photos: Optional[bool] = Query(None),
    source: Optional[str] = Query(None),
    sort_by: str = Query("price", pattern="^(price|area|rooms|floor|first_seen|last_seen)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
) -> StreamingResponse:
    """
    Экспортировать результаты поиска в выбранном формате.
    
    Args:
        format: Формат экспорта (csv, json, jsonl)
        city: Город для поиска
        property_type: Тип недвижимости
        min_price: Минимальная цена
        max_price: Максимальная цена
        min_rooms: Минимальное количество комнат
        max_rooms: Максимальное количество комнат
        min_area: Минимальная площадь
        max_area: Максимальная площадь
        district: Район
        has_photos: Фильтр по фотографиям
        source: Источник
        sort_by: Поле для сортировки
        sort_order: Порядок сортировки
        
    Returns:
        StreamingResponse с файлом
    """
    try:
        # Начинаем таймер для метрик
        start_time = time.time()
        
        # Валидация формата
        if format not in ["csv", "json", "jsonl"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid format: {format}. Supported formats: csv, json, jsonl"
            )
        
        # Получаем свойства
        search_service = OptimizedSearchService()
        all_properties, is_cached, stats = await search_service.search_cached(city, property_type)
        
        # Применяем фильтры
        property_filter = PropertyFilter(
            min_price=min_price,
            max_price=max_price,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            min_area=min_area,
            max_area=max_area,
            district=district,
            has_photos=has_photos,
            source=source,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        
        # Ограничиваем максимальное количество экспортируемых записей (защита от перегрузки)
        MAX_EXPORT_ITEMS = 10000
        filtered_properties, total = property_filter.filter(all_properties, skip=0, limit=MAX_EXPORT_ITEMS)
        
        # Предупреждаем если записей больше лимита
        if total > MAX_EXPORT_ITEMS:
            logger.warning(f"Export limited to {MAX_EXPORT_ITEMS} items (total: {total})")
        
        # Экспортируем в выбранном формате
        export_service = ExportService()
        
        # Log cache statistics
        logger.info(f"Export for {city} completed. Properties exported: {len(filtered_properties)}. Cache hit: {is_cached}")
        
        if format == "csv":
            content = export_service.to_csv(filtered_properties)
            media_type = "text/csv"
            filename = f"properties_{city.lower()}.csv"
        elif format == "jsonl":
            content = export_service.to_jsonl(filtered_properties)
            media_type = "application/x-ndjson"
            filename = f"properties_{city.lower()}.jsonl"
        else:  # json
            content = export_service.to_json(filtered_properties, pretty=True)
            media_type = "application/json"
            filename = f"properties_{city.lower()}.json"
        
        # Записываем метрики экспорта
        duration = time.time() - start_time
        metrics_collector.record_export(
            format=format,
            status="success",
            duration=duration,
            items_count=len(filtered_properties)
        )
        
        logger.info(f"Exporting {len(filtered_properties)} properties to {format} for {city}")
        
        # Преобразуем строку в BytesIO для StreamingResponse
        output = io.BytesIO(content.encode("utf-8"))
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
        
    except Exception as e:
        # Записываем метрику ошибки
        duration = time.time() - start_time
        metrics_collector.record_export(
            format=format,
            status="error",
            duration=duration,
            items_count=0
        )
        
        logger.error(f"Export error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {str(e)}",
        )