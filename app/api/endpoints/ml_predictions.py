"""
API endpoints для ML предсказаний и аналитики цен.
"""

from typing import Optional
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.price_predictor import price_predictor, PricePrediction
from app.utils.logger import logger
from app.db.models.session import get_db

router = APIRouter(prefix="/ml", tags=["ml-predictions"])


# ============================================================================
# Pydantic Models
# ============================================================================

class PricePredictionRequest(BaseModel):
    """Запрос на предсказание цены."""
    city: str = Field(..., description="Город")
    rooms: int = Field(..., ge=0, le=10, description="Количество комнат")
    area: float = Field(..., ge=10, le=500, description="Площадь в м²")
    district: Optional[str] = Field(None, description="Район")
    floor: Optional[int] = Field(None, ge=1, description="Этаж")
    total_floors: Optional[int] = Field(None, ge=1, description="Всего этажей")
    is_verified: bool = Field(False, description="Верифицировано ли объявление")


class PricePredictionResponse(BaseModel):
    """Ответ с предсказанием цены."""
    predicted_price: float
    confidence: float
    price_range: tuple[float, float]
    factors: dict
    trend: str
    recommendation: str


class PriceComparisonRequest(BaseModel):
    """Запрос на сравнение цены."""
    actual_price: float = Field(..., ge=0)
    city: str
    rooms: int
    area: float
    district: Optional[str] = None


class PriceComparisonResponse(BaseModel):
    """Ответ на сравнение цены."""
    actual_price: float
    predicted_price: float
    difference: float
    percentage_difference: float
    rating: str
    comment: str


class OptimalPriceResponse(BaseModel):
    """Ответ с оптимальным диапазоном цен."""
    optimal_price: float
    min_competitive: float
    max_competitive: float
    market_average: float
    confidence: float


class MarketTrendResponse(BaseModel):
    """Ответ с трендом рынка."""
    city: str
    rooms: Optional[int]
    trend: str
    comment: str
    stats_7_days: dict
    stats_30_days: dict
    change_percentage: float


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/predict-price", response_model=PricePredictionResponse)
async def predict_price(request: PricePredictionRequest, db: AsyncSession = Depends(get_db)):
    """
    Предсказать цену аренды на основе характеристик.
    
    **Использует ML модель** для оценки справедливой цены.
    
    **Учитывает:**
    - Город и район
    - Площадь и количество комнат
    - Этаж
    - Верификацию
    - Исторические данные
    
    **Возвращает:**
    - Предсказанную цену
    - Уверенность модели (0-1)
    - Диапазон цен
    - Факторы влияния
    - Тренд рынка
    - Рекомендацию
    """
    # Load historical data for better predictions
    price_predictor.load_from_database(db, request.city, days=60)
    
    prediction = price_predictor.predict_price(
        city=request.city,
        rooms=request.rooms,
        area=request.area,
        district=request.district,
        floor=request.floor,
        total_floors=request.total_floors,
        is_verified=request.is_verified,
    )
    
    return {
        "predicted_price": prediction.predicted_price,
        "confidence": prediction.confidence,
        "price_range": prediction.price_range,
        "factors": prediction.factors,
        "trend": prediction.trend,
        "recommendation": prediction.recommendation,
    }


@router.get("/price-statistics/{city}")
async def get_price_statistics(
    city: str,
    rooms: Optional[int] = Query(None, ge=0, le=10),
    days: int = Query(60, ge=1, le=365, description="Период в днях"),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить статистику цен за период.
    
    **Параметры:**
    - `city` - город
    - `rooms` - количество комнат (опционально)
    - `days` - период для анализа (по умолчанию 60)
    
    **Возвращает:**
    - Количество объявлений
    - Средняя/минимальная/максимальная цена
    - Медиана
    - Стандартное отклонение
    """
    # Load data from database
    price_predictor.load_from_database(db, city, days=days, rooms=rooms)
    
    stats = price_predictor.get_price_statistics(
        city=city,
        rooms=rooms,
        days=days,
    )
    
    return stats


@router.post("/compare-price", response_model=PriceComparisonResponse)
async def compare_price(request: PriceComparisonRequest, db: AsyncSession = Depends(get_db)):
    """
    Сравнить реальную цену с рыночной.
    
    **Использует ML модель** для оценки справедливости цены.
    
    **Возвращает:**
    - Реальная vs предсказанная цена
    - Разница в рублях и процентах
    - Рейтинг (excellent/good/overpriced/underpriced)
    - Комментарий
    """
    # Load historical data for better predictions
    price_predictor.load_from_database(db, request.city, days=60)
    
    # Предсказываем рыночную цену
    prediction = price_predictor.predict_price(
        city=request.city,
        rooms=request.rooms,
        area=request.area,
        district=request.district,
    )
    
    # Сравниваем
    comparison = price_predictor.compare_price(
        actual_price=request.actual_price,
        predicted_price=prediction.predicted_price,
    )
    
    return comparison


@router.get("/optimal-price/{city}", response_model=OptimalPriceResponse)
async def get_optimal_price(
    city: str,
    rooms: int = Query(..., ge=0, le=10),
    area: float = Query(..., ge=10, le=500),
    district: Optional[str] = Query(None),
    floor: Optional[int] = Query(None, ge=1),
    total_floors: Optional[int] = Query(None, ge=1),
    is_verified: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить оптимальный диапазон цен для быстрой аренды.
    
    **Рекомендации:**
    - Оптимальная цена (немного ниже рынка)
    - Минимальная конкурентная
    - Максимальная конкурентная
    - Средняя рыночная
    
    Помогает определить цену для быстрой сдачи квартиры.
    """
    # Load historical data for better predictions
    price_predictor.load_from_database(db, city, days=60)
    
    optimal = price_predictor.get_optimal_price_range(
        city=city,
        rooms=rooms,
        area=area,
        district=district,
        floor=floor,
        total_floors=total_floors,
        is_verified=is_verified,
    )
    
    return optimal


@router.get("/market-trends/{city}", response_model=MarketTrendResponse)
async def get_market_trends(
    city: str,
    rooms: Optional[int] = Query(None, ge=0, le=10),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить тренды рынка для города.
    
    **Анализирует:**
    - Динамику цен
    - Направление тренда (рост/падение/стабильность)
    - Статистику по типам объявлений
    
    **Возвращает:**
    - Общий тренд
    - Статистику
    - Рекомендации
    """
    # Load historical data
    price_predictor.load_from_database(db, city, days=60, rooms=rooms)
    
    # Получаем статистику за разные периоды
    stats_7d = price_predictor.get_price_statistics(city, rooms, days=7)
    stats_30d = price_predictor.get_price_statistics(city, rooms, days=30)
    
    # Определяем тренд
    if stats_7d["avg_price"] > 0 and stats_30d["avg_price"] > 0:
        change = ((stats_7d["avg_price"] - stats_30d["avg_price"]) 
                  / stats_30d["avg_price"] * 100)
        
        if change > 5:
            trend = "increasing"
            comment = f"Цены растут (+{change:.1f}% за месяц)"
        elif change < -5:
            trend = "decreasing"
            comment = f"Цены снижаются ({change:.1f}% за месяц)"
        else:
            trend = "stable"
            comment = "Рынок стабилен"
    else:
        trend = "unknown"
        comment = "Недостаточно данных для анализа"
    
    return {
        "city": city,
        "rooms": rooms,
        "trend": trend,
        "comment": comment,
        "stats_7_days": stats_7d,
        "stats_30_days": stats_30d,
        "change_percentage": change if 'change' in locals() else 0,
    }


@router.get("/health")
async def ml_health():
    """Проверить статус ML сервиса."""
    return {
        "status": "healthy",
        "service": "ml-predictions",
        "features": [
            "price_prediction",
            "price_comparison",
            "market_trends",
            "optimal_pricing",
            "statistics",
        ],
        "model": "Ensemble (LinearRegression + RandomForest)",
        "history_size": len(price_predictor.history),
        "model_trained": getattr(price_predictor, 'model_trained', False),
        "model_performance": getattr(price_predictor, 'model_performance', {}),
    }