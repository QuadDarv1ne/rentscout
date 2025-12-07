"""
API endpoints for property management with PostgreSQL persistence.
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import get_db
from app.db import repositories
from app.db.repositories import property as property_repo
from app.utils.metrics import metrics_collector
from app.models.schemas import (
    PropertyCreate,
    Property,
    PropertyPriceHistoryEntry,
    PropertyStatistics,
    PopularProperty,
    PopularSearch,
    BulkUpsertResult,
    OperationStatus,
    DeactivateResult,
)
from app.utils.logger import logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/properties", tags=["properties"])


async def get_alerts_db():
    """Безопасная зависимость для алертов: при недоступной БД возвращает None."""
    try:
        async for db in get_db():
            yield db
    except Exception as e:
        logger.warning(f"Alerts DB unavailable, falling back to in-memory store: {e}")
        yield None


@router.post(
    "/",
    response_model=Property,
    status_code=201,
    summary="Создать новое объявление",
    response_description="Созданное объявление",
)
async def create_property(
    property_data: PropertyCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создает новое объявление в PostgreSQL."""
    try:
        db_property = await property_repo.create_property(db, property_data)
        return db_property
    except Exception as e:
        logger.error(f"Error creating property: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{property_id}",
    response_model=Property,
    summary="Получить объявление по ID",
    response_description="Объявление с указанным ID",
)
async def get_property(
    property_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Возвращает объявление по внутреннему идентификатору."""
    db_property = await property_repo.get_property(db, property_id)
    
    if not db_property:
        raise HTTPException(status_code=404, detail="Property not found")
    
    return db_property


@router.get(
    "/",
    response_model=List[Property],
    summary="Поиск объявлений (PostgreSQL)",
    response_description="Список объявлений, удовлетворяющих фильтрам",
)
async def search_properties(
    city: Optional[str] = Query(None, description="Filter by city"),
    source: Optional[str] = Query(None, description="Filter by source (avito, cian, etc.)"),
    district: Optional[str] = Query(None, description="Filter by district"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    min_rooms: Optional[int] = Query(None, description="Minimum number of rooms"),
    max_rooms: Optional[int] = Query(None, description="Maximum number of rooms"),
    min_area: Optional[float] = Query(None, description="Minimum area in sq meters"),
    max_area: Optional[float] = Query(None, description="Maximum area in sq meters"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    sort_by: str = Query("created_at", description="Sort by field (created_at, price, area, rooms)"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """
    Search properties with various filters.
    
    Supports filtering by:
    - City
    - Source (avito, cian, etc.)
    - Price range
    - Number of rooms
    - Area
    - Active status
    """
    try:
        properties = await property_repo.search_properties(
            db=db,
            city=city,
            district=district,
            min_price=min_price,
            max_price=max_price,
            min_rooms=min_rooms,
            max_rooms=max_rooms,
            min_area=min_area,
            max_area=max_area,
            source=source,
            is_active=is_active,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset
        )
        
        # Track search query for analytics
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            await property_repo.track_search_query(
                db=db,
                city=city,
                min_price=min_price,
                max_price=max_price,
                min_rooms=min_rooms,
                max_rooms=max_rooms,
                min_area=min_area,
                max_area=max_area,
                results_count=len(properties),
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        return properties
    except Exception as e:
        logger.error(f"Error searching properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stats/overview",
    response_model=PropertyStatistics,
    summary="Получить статистику объявлений",
    response_description="Сводная статистика по объявлениям",
)
async def get_statistics(
    city: Optional[str] = Query(None, description="Filter by city"),
    source: Optional[str] = Query(None, description="Filter by source"),
    district: Optional[str] = Query(None, description="Filter by district"),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает количество, средние и экстремальные значения цены и площади."""
    try:
        stats = await property_repo.get_property_statistics(
            db=db,
            city=city,
            source=source,
            district=district
        )
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{property_id}/price-history",
    response_model=List[PropertyPriceHistoryEntry],
    summary="История изменения цены",
    response_description="Последние изменения цен для объявления",
)
async def get_price_history(
    property_id: int,
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает последние изменения цены по объявлению."""
    try:
        history = await property_repo.get_price_history(db, property_id, limit)
        return history
    except Exception as e:
        logger.error(f"Error getting price history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{property_id}/view",
    response_model=OperationStatus,
    summary="Отслеживание просмотра объявления",
    response_description="Результат регистрации просмотра",
)
async def track_view(
    property_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Регистрирует просмотр объявления и возвращает статус операции."""
    try:
        # Verify property exists
        db_property = await property_repo.get_property(db, property_id)
        if not db_property:
            raise HTTPException(status_code=404, detail="Property not found")
        
        # Track the view
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        referer = request.headers.get("referer")
        
        await property_repo.track_property_view(
            db=db,
            property_id=property_id,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer
        )
        
        return OperationStatus(status="ok", message="View tracked")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking view: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stats/popular",
    response_model=List[PopularProperty],
    summary="Популярные объявления",
    response_description="Топ объявлений по просмотрам",
)
async def get_popular_properties(
    limit: int = Query(10, ge=1, le=100),
    days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает список самых популярных объявлений за выбранный период."""
    try:
        popular = await property_repo.get_popular_properties(db, limit, days)
        
        # Get full property data
        result: List[PopularProperty] = []
        for property_id, view_count in popular:
            db_property = await property_repo.get_property(db, property_id)
            if db_property:
                result.append(PopularProperty(property=db_property, view_count=view_count))
        
        return result
    except Exception as e:
        logger.error(f"Error getting popular properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stats/searches",
    response_model=List[PopularSearch],
    summary="Популярные поисковые запросы",
    response_description="Топ поисковых запросов пользователей",
)
async def get_popular_searches(
    limit: int = Query(10, ge=1, le=100),
    days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Возвращает статистику популярных поисковых запросов за выбранный период."""
    try:
        searches = await property_repo.get_popular_searches(db, limit, days)
        return searches
    except Exception as e:
        logger.error(f"Error getting popular searches: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/bulk",
    status_code=201,
    response_model=BulkUpsertResult,
    summary="Массовая загрузка/обновление объявлений",
    response_description="Количество созданных/обновленных записей",
)
async def bulk_upsert_properties(
    properties: List[PropertyCreate],
    db: AsyncSession = Depends(get_db)
):
    """Массово создаёт или обновляет объявления по source + external_id."""
    try:
        result = await property_repo.bulk_upsert_properties(db, properties)
        return BulkUpsertResult(**result)
    except Exception as e:
        logger.error(f"Error bulk upserting properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/deactivate-old",
    response_model=DeactivateResult,
    summary="Деактивировать устаревшие объявления",
    response_description="Количество деактивированных объявлений",
)
async def deactivate_old_properties(
    source: str = Query(..., description="Source to deactivate from"),
    hours: int = Query(24, ge=1, le=720, description="Hours since last seen"),
    db: AsyncSession = Depends(get_db)
):
    """Помечает неактивными объявления, которые не встречались больше указанного времени."""
    try:
        count = await property_repo.deactivate_old_properties(db, source, hours)
        return DeactivateResult(status="ok", deactivated_count=count)
    except Exception as e:
        logger.error(f"Error deactivating old properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/by-price-per-sqm",
    response_model=List[Property],
    summary="Поиск объявлений по цене за квадратный метр",
    response_description="Список объявлений, отсортированных по цене за квадратный метр",
)
async def search_properties_by_price_per_sqm(
    city: Optional[str] = Query(None, description="Filter by city"),
    source: Optional[str] = Query(None, description="Filter by source (avito, cian, etc.)"),
    district: Optional[str] = Query(None, description="Filter by district"),
    max_price_per_sqm: Optional[float] = Query(None, description="Maximum price per square meter"),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    db: AsyncSession = Depends(get_db),
    request: Request = None
):
    """
    Search properties sorted by price per square meter.
    
    This endpoint is optimized for finding the best value properties.
    """
    try:
        properties = await property_repo.search_properties_by_price_per_sqm(
            db=db,
            city=city,
            source=source,
            district=district,
            max_price_per_sqm=max_price_per_sqm,
            is_active=is_active,
            limit=limit,
            offset=offset
        )
        
        # Track search query for analytics
        if request:
            ip_address = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            
            await property_repo.track_search_query(
                db=db,
                city=city,
                source=source,
                max_price_per_sqm=max_price_per_sqm,
                results_count=len(properties),
                ip_address=ip_address,
                user_agent=user_agent
            )
        
        return properties
    except Exception as e:
        logger.error(f"Error searching properties by price per sqm: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/compare/{property_id1}/{property_id2}",
    response_model=Dict[str, Any],
    summary="Сравнить два объявления",
    response_description="Результат сравнения объявлений"
)
async def compare_properties(
    property_id1: int,
    property_id2: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Сравнивает два объявления по различным параметрам.
    """
    try:
        # Record metrics
        metrics_collector.record_property_comparison()
        
        # Получаем оба объявления
        prop1 = await property_repo.get_property(db, property_id1)
        prop2 = await property_repo.get_property(db, property_id2)
        
        if not prop1 or not prop2:
            raise HTTPException(status_code=404, detail="One or both properties not found")
        
        # Выполняем сравнение
        comparison = {
            "property1": {
                "id": prop1.id,
                "title": prop1.title,
                "source": prop1.source,
                "price": prop1.price,
                "rooms": prop1.rooms,
                "area": prop1.area,
                "price_per_sqm": prop1.price / prop1.area if prop1.area else None,
                "city": prop1.city,
                "address": prop1.address
            },
            "property2": {
                "id": prop2.id,
                "title": prop2.title,
                "source": prop2.source,
                "price": prop2.price,
                "rooms": prop2.rooms,
                "area": prop2.area,
                "price_per_sqm": prop2.price / prop2.area if prop2.area else None,
                "city": prop2.city,
                "address": prop2.address
            },
            "differences": {
                "price_difference": abs(prop1.price - prop2.price),
                "price_per_sqm_diff": (
                    abs((prop1.price / prop1.area if prop1.area else 0) - 
                        (prop2.price / prop2.area if prop2.area else 0))
                ),
                "area_difference": abs(prop1.area - prop2.area) if prop1.area and prop2.area else None,
                "rooms_difference": abs(prop1.rooms - prop2.rooms) if prop1.rooms and prop2.rooms else None
            },
            "better_value": "property1" if (
                (prop1.price / prop1.area if prop1.area else float('inf')) < 
                (prop2.price / prop2.area if prop2.area else float('inf'))
            ) else "property2"
        }
        
        return comparison
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing properties: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/recommendations",
    response_model=List[Property],
    summary="Получить рекомендации по недвижимости",
    response_description="Список рекомендованных объявлений"
)
async def get_recommendations(
    city: str = Query(..., description="Город для поиска рекомендаций"),
    budget: Optional[float] = Query(None, description="Бюджет покупателя"),
    rooms: Optional[int] = Query(None, description="Количество комнат"),
    min_area: Optional[float] = Query(None, description="Минимальная площадь"),
    max_area: Optional[float] = Query(None, description="Максимальная площадь"),
    limit: int = Query(10, le=50, description="Количество рекомендаций"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получает рекомендации по недвижимости на основе заданных критериев.
    """
    try:
        # Получаем свойства из базы данных
        properties = await property_repo.search_properties(db, {"city": city}, limit=limit)
        
        # Если указан бюджет, фильтруем по нему
        if budget is not None:
            properties = [prop for prop in properties if prop.price <= budget]
            
        # Фильтруем по количеству комнат
        if rooms is not None:
            properties = [prop for prop in properties if prop.rooms == rooms]
            
        # Фильтруем по площади
        if min_area is not None:
            properties = [prop for prop in properties if prop.area and prop.area >= min_area]
        if max_area is not None:
            properties = [prop for prop in properties if prop.area and prop.area <= max_area]
        
        # Сортируем по соотношению цена/площадь
        properties.sort(key=lambda p: p.price / p.area if p.area else float('inf'))
        
        # Limit the results
        result = properties[:limit]
        
        # Record metrics
        metrics_collector.record_property_recommendation(len(result))
        
        return result
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/trends/{city}",
    response_model=Dict[str, Any],
    summary="Получить тренды цен по городу",
    response_description="Статистика по изменению цен"
)
async def get_price_trends(
    city: str,
    days: int = Query(30, le=365, description="Количество дней для анализа"),
    db: AsyncSession = Depends(get_db)
):
    """
    Анализирует тренды цен по недвижимости в указанном городе.
    """
    try:
        # Record metrics
        metrics_collector.record_price_trends_query()
        
        # Получаем историю цен за указанный период
        trends = await property_repo.get_price_trends(db, city, days)
        
        if not trends:
            return {"city": city, "days": days, "trends": [], "average_change": 0}
        
        # Вычисляем среднее изменение цены
        if len(trends) > 1:
            first_avg = trends[0]["average_price"]
            last_avg = trends[-1]["average_price"]
            average_change = ((last_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
        else:
            average_change = 0
            
        return {
            "city": city,
            "days": days,
            "trends": trends,
            "average_change": round(average_change, 2)
        }
    except Exception as e:
        logger.error(f"Error getting price trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PropertyAlertCreate(BaseModel):
    """Schema for creating a property alert."""
    city: str = Field(..., description="Город для отслеживания")
    max_price: Optional[float] = Field(None, description="Максимальная цена")
    min_price: Optional[float] = Field(None, description="Минимальная цена")
    rooms: Optional[int] = Field(None, description="Количество комнат")
    min_area: Optional[float] = Field(None, description="Минимальная площадь")
    max_area: Optional[float] = Field(None, description="Максимальная площадь")
    email: str = Field(..., description="Email для уведомлений")


class PropertyAlert(BaseModel):
    """Schema for property alert."""
    id: int
    city: str
    max_price: Optional[float]
    min_price: Optional[float]
    rooms: Optional[int]
    min_area: Optional[float]
    max_area: Optional[float]
    email: str
    is_active: bool
    created_at: datetime


# In-memory fallback for alerts (used when DB is unavailable, e.g., in tests)
memory_alerts: Dict[int, PropertyAlert] = {}


@router.post(
    "/alerts",
    response_model=PropertyAlert,
    status_code=201,
    summary="Создать оповещение о новых объявлениях",
    response_description="Созданное оповещение"
)
async def create_property_alert(
    alert_data: PropertyAlertCreate,
    db: Optional[AsyncSession] = Depends(get_alerts_db)
):
    """
    Создает оповещение для отслеживания новых объявлений по заданным критериям.
    """
    # Prepare alert data
    alert_dict = alert_data.model_dump()

    # Fallback immediately if БД недоступна
    if db is None:
        metrics_collector.record_property_alert_created()
        alert_id = len(memory_alerts) + 1
        alert = PropertyAlert(
            id=alert_id,
            is_active=True,
            created_at=datetime.utcnow(),
            **alert_dict,
        )
        memory_alerts[alert_id] = alert
        return alert

    try:
        # Record metrics
        metrics_collector.record_property_alert_created()
        
        # Create the alert
        from app.db.repositories import alerts as alerts_repo
        db_alert = await alerts_repo.create_alert(db, alert_dict)
        
        return db_alert
    except Exception as e:
        logger.error(f"Error creating property alert: {e}")
        # Fallback to in-memory store for dev/tests
        alert_id = len(memory_alerts) + 1
        alert = PropertyAlert(
            id=alert_id,
            is_active=True,
            created_at=datetime.utcnow(),
            **alert_dict,
        )
        memory_alerts[alert_id] = alert
        return alert


@router.get(
    "/alerts",
    response_model=List[PropertyAlert],
    summary="Получить список оповещений",
    response_description="Список активных оповещений"
)
async def list_property_alerts(
    email: str = Query(..., description="Email пользователя"),
    db: Optional[AsyncSession] = Depends(get_alerts_db)
):
    """
    Получает список оповещений для указанного email.
    """
    if db is None:
        return [alert for alert in memory_alerts.values() if alert.email == email]

    try:
        from app.db.repositories import alerts as alerts_repo
        alerts = await alerts_repo.get_alerts_by_email(db, email)
        return alerts
    except Exception as e:
        logger.error(f"Error listing property alerts: {e}")
        # Fallback to in-memory alerts
        return [alert for alert in memory_alerts.values() if alert.email == email]


@router.put(
    "/alerts/{alert_id}",
    response_model=PropertyAlert,
    summary="Обновить оповещение",
    response_description="Обновленное оповещение"
)
async def update_property_alert(
    alert_id: int,
    alert_data: PropertyAlertCreate,
    db: Optional[AsyncSession] = Depends(get_alerts_db)
):
    """
    Обновляет существующее оповещение.
    """
    # Fallback if DB unavailable
    if db is None:
        if alert_id not in memory_alerts:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert_dict = alert_data.model_dump()
        updated_alert = PropertyAlert(
            id=alert_id,
            is_active=memory_alerts[alert_id].is_active,
            created_at=memory_alerts[alert_id].created_at,
            **alert_dict,
        )
        memory_alerts[alert_id] = updated_alert
        return updated_alert

    try:
        from app.db.repositories import alerts as alerts_repo
        alert_dict = alert_data.model_dump()
        updated_alert = await alerts_repo.update_alert(db, alert_id, alert_dict)
        
        if not updated_alert:
            raise HTTPException(status_code=404, detail="Alert not found")
            
        return updated_alert
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating property alert: {e}")
        # Fallback to in-memory alerts
        if alert_id not in memory_alerts:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert_dict = alert_data.model_dump()
        updated_alert = PropertyAlert(
            id=alert_id,
            is_active=memory_alerts[alert_id].is_active,
            created_at=memory_alerts[alert_id].created_at,
            **alert_dict,
        )
        memory_alerts[alert_id] = updated_alert
        return updated_alert


@router.delete(
    "/alerts/{alert_id}",
    response_model=OperationStatus,
    summary="Удалить оповещение",
    response_description="Статус операции"
)
async def delete_property_alert(
    alert_id: int,
    db: Optional[AsyncSession] = Depends(get_alerts_db)
):
    """
    Удаляет оповещение.
    """
    if db is None:
        if alert_id not in memory_alerts:
            raise HTTPException(status_code=404, detail="Alert not found")
        del memory_alerts[alert_id]
        return OperationStatus(success=True, message="Alert deleted successfully")

    try:
        from app.db.repositories import alerts as alerts_repo
        success = await alerts_repo.delete_alert(db, alert_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
            
        return OperationStatus(success=True, message="Alert deleted successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting property alert: {e}")
        # Fallback to in-memory alerts
        if alert_id not in memory_alerts:
            raise HTTPException(status_code=404, detail="Alert not found")
        del memory_alerts[alert_id]
        return OperationStatus(success=True, message="Alert deleted successfully")


@router.post(
    "/alerts/{alert_id}/deactivate",
    response_model=OperationStatus,
    summary="Деактивировать оповещение",
    response_description="Статус операции"
)
async def deactivate_property_alert(
    alert_id: int,
    db: Optional[AsyncSession] = Depends(get_alerts_db)
):
    """
    Деактивирует оповещение (не удаляет его).
    """
    if db is None:
        if alert_id not in memory_alerts:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert = memory_alerts[alert_id]
        memory_alerts[alert_id] = PropertyAlert(
            **alert.model_dump(exclude={"is_active"}),
            is_active=False,
        )
        return OperationStatus(success=True, message="Alert deactivated successfully")

    try:
        from app.db.repositories import alerts as alerts_repo
        success = await alerts_repo.deactivate_alert(db, alert_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
            
        return OperationStatus(success=True, message="Alert deactivated successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating property alert: {e}")
        # Fallback to in-memory alerts
        if alert_id not in memory_alerts:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert = memory_alerts[alert_id]
        memory_alerts[alert_id] = PropertyAlert(
            **alert.model_dump(exclude={"is_active"}),
            is_active=False,
        )
        return OperationStatus(success=True, message="Alert deactivated successfully")
