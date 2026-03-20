"""
API для геолокации и работы с картами.

Возможности:
- Поиск ближайших объектов недвижимости
- Heatmap плотности объектов по районам
- Расчёт расстояний между объектами
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime, timezone

from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.repositories import property as property_repository
from app.dependencies.auth import get_current_user, TokenData, get_optional_current_user
from app.services.advanced_cache import cached

router = APIRouter(prefix="/geo", tags=["geolocation"])


# =============================================================================
# Pydantic Models
# =============================================================================

class LocationPoint(BaseModel):
    """Точка на карте (широта/долгота)."""
    latitude: float = Field(..., ge=-90, le=90, description="Широта")
    longitude: float = Field(..., ge=-180, le=180, description="Долгота")


class NearbyPropertiesRequest(BaseModel):
    """Запрос поиска ближайших объектов."""
    location: LocationPoint
    radius_km: float = Field(default=1.0, ge=0.1, le=50.0, description="Радиус поиска в км")
    limit: int = Field(default=20, ge=1, le=100, description="Максимум объектов")


class PropertyLocationItem(BaseModel):
    """Объект недвижимости с геоданными."""
    id: int
    title: str
    price: float
    area: float
    rooms: Optional[int]
    floor: Optional[int]
    latitude: Optional[float]
    longitude: Optional[float]
    address: Optional[str]
    distance_km: Optional[float]
    link: Optional[str]


class NearbyPropertiesResponse(BaseModel):
    """Ответ с ближайшими объектами."""
    center: LocationPoint
    radius_km: float
    total: int
    properties: List[PropertyLocationItem]


class HeatmapPoint(BaseModel):
    """Точка для heatmap."""
    latitude: float
    longitude: float
    count: int
    avg_price: float
    density: str  # "low", "medium", "high"


class HeatmapResponse(BaseModel):
    """Ответ heatmap плотности объектов."""
    bounds: Dict[str, LocationPoint]
    points: List[HeatmapPoint]
    generated_at: datetime


class DistanceRequest(BaseModel):
    """Запрос расчёта расстояния."""
    from_location: LocationPoint
    to_location: LocationPoint


class DistanceResponse(BaseModel):
    """Ответ с расстоянием."""
    from_location: LocationPoint
    to_location: LocationPoint
    distance_km: float
    walking_time_min: int
    cycling_time_min: int


# =============================================================================
# Helper Functions
# =============================================================================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Вычисляет расстояние между двумя точками по формуле Haversine.
    
    Returns:
        Расстояние в километрах
    """
    R = 6371  # Радиус Земли в км
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return R * c


def estimate_walking_time(distance_km: float) -> int:
    """Оценивает время пешком (5 км/ч)."""
    return int(distance_km / 5 * 60)


def estimate_cycling_time(distance_km: float) -> int:
    """Оценивает время на велосипеде (15 км/ч)."""
    return int(distance_km / 15 * 60)


def get_density_label(count: int) -> str:
    """Определяет уровень плотности."""
    if count < 10:
        return "low"
    elif count < 50:
        return "medium"
    else:
        return "high"


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/nearby",
    response_model=NearbyPropertiesResponse,
    summary="Поиск ближайших объектов",
)
@cached(expire=300)  # Кеш на 5 минут
async def get_nearby_properties(
    request: NearbyPropertiesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_optional_current_user)
) -> NearbyPropertiesResponse:
    """
    Ищет объекты недвижимости в указанном радиусе от точки.
    
    ### Параметры:
    - **location**: Координаты центра поиска
    - **radius_km**: Радиус поиска (0.1-50 км)
    - **limit**: Максимум объектов (1-100)
    
    ### Возвращает:
    Список объектов с расстоянием от центра
    """
    # Получаем все объекты из БД (в production нужен spatial index)
    try:
        properties = await property_repository.get_all_properties(db, limit=500)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения объектов: {str(e)}"
        )
    
    # Фильтруем по расстоянию
    nearby = []
    for prop in properties:
        if prop.latitude and prop.longitude:
            distance = haversine_distance(
                request.location.latitude,
                request.location.longitude,
                prop.latitude,
                prop.longitude
            )
            
            if distance <= request.radius_km:
                nearby.append({
                    "id": prop.id,
                    "title": prop.title,
                    "price": prop.price,
                    "area": prop.area,
                    "rooms": prop.rooms,
                    "floor": prop.floor,
                    "latitude": prop.latitude,
                    "longitude": prop.longitude,
                    "address": prop.address,
                    "distance_km": round(distance, 2),
                    "link": prop.link,
                })
    
    # Сортируем по расстоянию
    nearby.sort(key=lambda x: x["distance_km"])
    
    # Ограничиваем результат
    limited = nearby[:request.limit]
    
    return NearbyPropertiesResponse(
        center=request.location,
        radius_km=request.radius_km,
        total=len(nearby),
        properties=[PropertyLocationItem(**p) for p in limited]
    )


@router.get(
    "/heatmap",
    response_model=HeatmapResponse,
    summary="Heatmap плотности объектов",
)
@cached(expire=600)  # Кеш на 10 минут
async def get_heatmap(
    city: str = Query(default="Москва", description="Город"),
    grid_size: float = Query(default=0.01, ge=0.001, le=0.1, description="Размер сетки в градусах"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[TokenData] = Depends(get_optional_current_user)
) -> HeatmapResponse:
    """
    Генерирует heatmap плотности объектов недвижимости.
    
    ### Параметры:
    - **city**: Город для анализа
    - **grid_size**: Размер ячейки сетки (градусы)
    
    ### Возвращает:
    Сетка точек с плотностью и средней ценой
    """
    # Координаты городов (в production нужен геокодер)
    city_bounds = {
        "Москва": {
            "north": 55.95, "south": 55.55,
            "east": 37.95, "west": 37.35
        },
        "Санкт-Петербург": {
            "north": 60.15, "south": 59.75,
            "east": 30.55, "west": 29.85
        }
    }
    
    bounds = city_bounds.get(city, city_bounds["Москва"])
    
    try:
        properties = await property_repository.get_all_properties(db, limit=1000)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения объектов: {str(e)}"
        )
    
    # Создаём сетку
    grid: Dict[tuple, List[dict]] = {}
    
    for prop in properties:
        if prop.latitude and prop.longitude:
            # Округляем координаты до размера сетки
            lat_key = round(prop.latitude / grid_size) * grid_size
            lon_key = round(prop.longitude / grid_size) * grid_size
            
            key = (lat_key, lon_key)
            if key not in grid:
                grid[key] = []
            grid[key].append({
                "price": prop.price,
                "latitude": prop.latitude,
                "longitude": prop.longitude
            })
    
    # Формируем точки heatmap
    points = []
    for (lat, lon), props in grid.items():
        count = len(props)
        avg_price = sum(p["price"] for p in props) / count if count > 0 else 0
        
        points.append(HeatmapPoint(
            latitude=lat,
            longitude=lon,
            count=count,
            avg_price=round(avg_price, 2),
            density=get_density_label(count)
        ))
    
    # Сортируем по плотности
    points.sort(key=lambda x: x.count, reverse=True)
    
    return HeatmapResponse(
        bounds={
            "north": LocationPoint(latitude=bounds["north"], longitude=bounds["west"]),
            "south": LocationPoint(latitude=bounds["south"], longitude=bounds["east"])
        },
        points=points,
        generated_at=datetime.now(timezone.utc)
    )


@router.post(
    "/distance",
    response_model=DistanceResponse,
    summary="Расчёт расстояния между точками",
)
async def calculate_distance(
    request: DistanceRequest
) -> DistanceResponse:
    """
    Вычисляет расстояние между двумя точками.
    
    ### Возвращает:
    - **distance_km**: Расстояние в километрах
    - **walking_time_min**: Время пешком (~5 км/ч)
    - **cycling_time_min**: Время на велосипеде (~15 км/ч)
    """
    distance = haversine_distance(
        request.from_location.latitude,
        request.from_location.longitude,
        request.to_location.latitude,
        request.to_location.longitude
    )
    
    return DistanceResponse(
        from_location=request.from_location,
        to_location=request.to_location,
        distance_km=round(distance, 2),
        walking_time_min=estimate_walking_time(distance),
        cycling_time_min=estimate_cycling_time(distance)
    )


@router.get(
    "/cities",
    summary="Список поддерживаемых городов",
)
async def get_supported_cities() -> Dict[str, Any]:
    """
    Возвращает список городов с координатами.
    """
    return {
        "cities": [
            {
                "name": "Москва",
                "center": {"latitude": 55.75, "longitude": 37.61},
                "bounds": {"north": 55.95, "south": 55.55, "east": 37.95, "west": 37.35}
            },
            {
                "name": "Санкт-Петербург",
                "center": {"latitude": 59.93, "longitude": 30.33},
                "bounds": {"north": 60.15, "south": 59.75, "east": 30.55, "west": 29.85}
            }
        ]
    }
