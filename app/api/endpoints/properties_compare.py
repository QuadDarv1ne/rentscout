"""
API для сравнения объектов недвижимости.

Позволяет сравнивать несколько объектов по параметрам:
- Цена и цена за м²
- Площадь, комнаты, этаж
- Расположение
- Характеристики
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories import property as property_repository
from app.dependencies.auth import get_current_user, TokenData

router = APIRouter(prefix="/properties", tags=["properties-comparison"])


class PropertyCompareRequest(BaseModel):
    """Запрос на сравнение объектов."""
    property_ids: List[int] = Field(..., min_items=2, max_items=5, description="ID объектов для сравнения")
    metrics: Optional[List[str]] = Field(
        default=["price", "area", "rooms", "floor", "location", "features"],
        description="Параметры для сравнения"
    )


class PropertyCompareItem(BaseModel):
    """Объект для сравнения."""
    id: int
    title: str
    price: float
    area: float
    rooms: Optional[int]
    floor: Optional[int]
    total_floors: Optional[int]
    city: Optional[str]
    district: Optional[str]
    price_per_sqm: Optional[float]
    link: Optional[str]
    photos: List[str]
    score: float = 0.0


class PropertyComparisonResponse(BaseModel):
    """Ответ сравнения объектов."""
    properties: List[PropertyCompareItem]
    best_value: Optional[int] = Field(None, description="ID лучшего по соотношению цена/качество")
    cheapest: Optional[int] = Field(None, description="ID самого дешёвого")
    largest: Optional[int] = Field(None, description="ID самого большого")
    recommendation: Optional[str] = Field(None, description="Рекомендация")
    comparison_table: Dict[str, List[Any]] = Field(default_factory=dict, description="Таблица сравнения")


def calculate_property_score(property_data: dict) -> float:
    """
    Рассчитывает общий score объекта.
    
    Учитывает:
    - Цену за м² (чем меньше, тем лучше)
    - Этаж (не первый и не последний)
    - Наличие фото
    - Проверенность
    """
    score = 50.0  # Базовый score
    
    # Цена за м² (нормализуем)
    price_per_sqm = property_data.get('price_per_sqm')
    if price_per_sqm:
        if price_per_sqm < 100000:
            score += 20
        elif price_per_sqm < 150000:
            score += 10
        elif price_per_sqm < 200000:
            score += 5
    
    # Этаж (предпочтительно не первый и не последний)
    floor = property_data.get('floor')
    total_floors = property_data.get('total_floors')
    if floor and total_floors:
        if floor > 1 and floor < total_floors:
            score += 15
        elif floor == 1:
            score -= 10
        elif floor == total_floors:
            score -= 5
    
    # Наличие фото
    photos = property_data.get('photos', [])
    if photos and len(photos) > 0:
        score += 10
    if photos and len(photos) > 5:
        score += 5
    
    # Проверенность
    if property_data.get('is_verified'):
        score += 10
    
    # Активность
    if property_data.get('is_active'):
        score += 5
    
    return min(100.0, max(0.0, score))


@router.post("/compare", response_model=PropertyComparisonResponse)
async def compare_properties(
    request: PropertyCompareRequest,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
) -> PropertyComparisonResponse:
    """
    Сравнить несколько объектов недвижимости.
    
    Сравнивает объекты по указанным метрикам и рекомендует лучший вариант.
    """
    # Получаем объекты из БД
    properties = []
    for prop_id in request.property_ids:
        prop = await property_repository.get_property_by_id(db, prop_id)
        if not prop:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Объект с ID {prop_id} не найден"
            )
        properties.append(prop)
    
    if len(properties) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для сравнения необходимо минимум 2 объекта"
        )
    
    # Конвертируем в формат для сравнения
    compare_items: List[PropertyCompareItem] = []
    
    for prop in properties:
        score = calculate_property_score({
            'price_per_sqm': prop.price_per_sqm,
            'floor': prop.floor,
            'total_floors': prop.total_floors,
            'photos': prop.photos or [],
            'is_verified': prop.is_verified,
            'is_active': prop.is_active,
        })
        
        item = PropertyCompareItem(
            id=prop.id,
            title=prop.title,
            price=prop.price,
            area=prop.area or 0,
            rooms=prop.rooms,
            floor=prop.floor,
            total_floors=prop.total_floors,
            city=prop.city,
            district=prop.district,
            price_per_sqm=prop.price_per_sqm,
            link=prop.link,
            photos=prop.photos or [],
            score=score,
        )
        compare_items.append(item)
    
    # Определяем лучший вариант
    best_value_id = max(compare_items, key=lambda x: x.score).id if compare_items else None
    cheapest_id = min(compare_items, key=lambda x: x.price).id if compare_items else None
    largest_id = max(compare_items, key=lambda x: x.area).id if compare_items else None
    
    # Формируем таблицу сравнения
    comparison_table = {
        "price": [item.price for item in compare_items],
        "area": [item.area for item in compare_items],
        "rooms": [item.rooms for item in compare_items],
        "floor": [f"{item.floor}/{item.total_floors}" if item.floor else "N/A" for item in compare_items],
        "price_per_sqm": [item.price_per_sqm for item in compare_items],
        "score": [item.score for item in compare_items],
    }
    
    # Формируем рекомендацию
    recommendation = None
    if best_value_id and cheapest_id and best_value_id == cheapest_id:
        recommendation = "Лучший по соотношению цена/качество и самый дешёвый вариант"
    elif best_value_id:
        best_item = next((i for i in compare_items if i.id == best_value_id), None)
        if best_item and best_item.score > 70:
            recommendation = f"Рекомендуемый вариант с высоким score ({best_item.score:.1f})"
        else:
            recommendation = "Лучший по соотношению цена/качество"
    
    return PropertyComparisonResponse(
        properties=compare_items,
        best_value=best_value_id,
        cheapest=cheapest_id,
        largest=largest_id,
        recommendation=recommendation,
        comparison_table=comparison_table,
    )


class PriceHistoryResponse(BaseModel):
    """Ответ с историей цен."""
    property_id: int
    history: List[Dict[str, Any]]
    trend: str  # "increasing", "decreasing", "stable"
    avg_change_percent: Optional[float]
    forecast: Optional[Dict[str, Any]]


@router.get("/{property_id}/price-history", response_model=PriceHistoryResponse)
async def get_property_price_history(
    property_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
) -> PriceHistoryResponse:
    """
    Получить историю изменения цены объекта.
    
    Возвращает всю историю изменений цены с трендом и прогнозом.
    """
    # Получаем объект
    prop = await property_repository.get_property_by_id(db, property_id)
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Объект с ID {property_id} не найден"
        )
    
    # Получаем историю цен
    history = await property_repository.get_property_price_history(db, property_id)
    
    history_data = []
    for entry in history or []:
        history_data.append({
            "date": entry.changed_at.isoformat() if entry.changed_at else None,
            "old_price": entry.old_price,
            "new_price": entry.new_price,
            "change": entry.price_change,
            "change_percent": entry.price_change_percent,
        })
    
    # Определяем тренд
    trend = "stable"
    avg_change_percent = None
    
    if history_data:
        changes = [h.get('change', 0) or 0 for h in history_data]
        avg_change = sum(changes) / len(changes)
        
        if avg_change > 0:
            trend = "increasing"
        elif avg_change < 0:
            trend = "decreasing"
        
        change_percents = [h.get('change_percent', 0) or 0 for h in history_data]
        avg_change_percent = sum(change_percents) / len(change_percents) if change_percents else None
    
    # Простой прогноз (линейная экстраполяция)
    forecast = None
    if history_data and len(history_data) >= 2:
        last_price = prop.price
        if avg_change_percent is not None:
            forecast_price = last_price * (1 + avg_change_percent / 100)
            forecast = {
                "next_month": round(forecast_price, 2),
                "confidence": "low" if abs(avg_change_percent or 0) > 10 else "medium",
                "trend": trend,
            }
    
    return PriceHistoryResponse(
        property_id=property_id,
        history=history_data,
        trend=trend,
        avg_change_percent=avg_change_percent,
        forecast=forecast,
    )


@router.get("/price-trends", response_model=Dict[str, Any])
async def get_price_trends(
    city: str = "Москва",
    property_type: str = "Квартира",
    rooms: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Получить тренды цен по городу/типу недвижимости.
    
    Возвращает статистику и тренды цен за последний период.
    """
    from sqlalchemy import func, select
    from app.db.models.property import Property
    from datetime import datetime, timedelta
    
    # Получаем статистику
    query = select(
        func.avg(Property.price).label('avg_price'),
        func.min(Property.price).label('min_price'),
        func.max(Property.price).label('max_price'),
        func.avg(Property.area).label('avg_area'),
        func.count(Property.id).label('total_count'),
    ).where(
        Property.city == city,
        Property.is_active == True,
    )
    
    if rooms:
        query = query.where(Property.rooms == rooms)
    
    result = await db.execute(query)
    stats = result.fetchone()
    
    if not stats or stats.total_count == 0:
        return {
            "city": city,
            "property_type": property_type,
            "rooms": rooms,
            "error": "Нет данных для указанного запроса",
        }
    
    # Получаем тренд по сравнению с прошлым месяцем
    one_month_ago = datetime.now() - timedelta(days=30)
    
    query_last_month = select(
        func.avg(Property.price).label('avg_price'),
    ).where(
        Property.city == city,
        Property.first_seen < one_month_ago,
        Property.is_active == True,
    )
    
    if rooms:
        query_last_month = query_last_month.where(Property.rooms == rooms)
    
    result_last_month = await db.execute(query_last_month)
    last_month_avg = result_last_month.scalar()
    
    current_avg = stats.avg_price or 0
    trend_percent = None
    
    if last_month_avg and last_month_avg > 0:
        trend_percent = ((current_avg - last_month_avg) / last_month_avg) * 100
    
    trend = "stable"
    if trend_percent:
        if trend_percent > 5:
            trend = "increasing"
        elif trend_percent < -5:
            trend = "decreasing"
    
    return {
        "city": city,
        "property_type": property_type,
        "rooms": rooms,
        "current_avg_price": round(current_avg, 2) if current_avg else None,
        "min_price": stats.min_price,
        "max_price": stats.max_price,
        "avg_area": round(stats.avg_area, 2) if stats.avg_area else None,
        "total_count": stats.total_count,
        "trend": trend,
        "trend_percent": round(trend_percent, 2) if trend_percent else None,
        "last_month_avg_price": round(last_month_avg, 2) if last_month_avg else None,
    }
