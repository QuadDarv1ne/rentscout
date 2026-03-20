"""
Mobile API - оптимизированные endpoints для мобильных клиентов.

Особенности:
- Минимальный payload size
- Пагинация с курсором
- Сжатие данных
- Быстрые запросы к БД
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from app.dependencies.auth import get_current_user, TokenData
from app.db.session import get_db
from app.db.repositories import property as property_repository
from app.db.repositories import user as user_repository
from app.utils.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func


router = APIRouter(prefix="/mobile", tags=["mobile"])


# =============================================================================
# Pydantic Models (Lightweight)
# =============================================================================

class PropertySummary(BaseModel):
    """Минимальная информация о property для мобильных клиентов."""
    id: int
    title: str
    price: int
    currency: str = "RUB"
    rooms: Optional[int] = None
    area: Optional[float] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    district: Optional[str] = None
    city: str
    property_type: str
    photo_url: Optional[str] = None


class PropertyListResponse(BaseModel):
    """Ответ с списком properties для мобильных клиентов."""
    items: List[PropertySummary]
    total: int
    page: int
    per_page: int
    has_next: bool
    next_cursor: Optional[str] = None


class PropertyDetailMobile(BaseModel):
    """Детальная информация для мобильных клиентов."""
    id: int
    title: str
    description: Optional[str] = None
    price: int
    currency: str = "RUB"
    rooms: Optional[int] = None
    area: Optional[float] = None
    floor: Optional[int] = None
    floors_total: Optional[int] = None
    district: Optional[str] = None
    city: str
    address: Optional[str] = None
    property_type: str
    photo_urls: List[str] = []
    source: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserProfile(BaseModel):
    """Профиль пользователя для мобильных клиентов."""
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime


class BookmarkMobile(BaseModel):
    """Упрощённая модель закладки."""
    id: int
    property_id: int
    created_at: datetime


class BookmarkListResponse(BaseModel):
    """Список закладок для мобильных клиентов."""
    items: List[BookmarkMobile]
    total: int


# =============================================================================
# Property Endpoints
# =============================================================================

@router.get(
    "/properties",
    response_model=PropertyListResponse,
    summary="Поиск объявлений (мобильная версия)",
)
async def mobile_search_properties(
    city: Optional[str] = Query(None, description="Фильтр по городу"),
    price_min: Optional[int] = Query(None, description="Мин. цена"),
    price_max: Optional[int] = Query(None, description="Макс. цена"),
    rooms: Optional[int] = Query(None, description="Количество комнат"),
    property_type: Optional[str] = Query(None, description="Тип недвижимости"),
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(20, ge=5, le=50, description="Элементов на странице"),
    cursor: Optional[str] = Query(None, description="Курсор для пагинации"),
    db: AsyncSession = Depends(get_db)
) -> PropertyListResponse:
    """
    Упрощённый поиск объявлений для мобильных приложений.
    
    Возвращает минимальный набор данных для быстрой загрузки.
    """
    # Вычисляем offset
    offset = (page - 1) * per_page
    
    # Базовый запрос
    query = select(property_repository.Property).where(
        property_repository.Property.is_active == True
    )
    
    # Фильтры
    if city:
        query = query.where(property_repository.Property.city.ilike(f"%{city}%"))
    if price_min:
        query = query.where(property_repository.Property.price >= price_min)
    if price_max:
        query = query.where(property_repository.Property.price <= price_max)
    if rooms:
        query = query.where(property_repository.Property.rooms == rooms)
    if property_type:
        query = query.where(property_repository.Property.property_type == property_type)
    
    # Получаем общее количество
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Получаем данные с пагинацией
    query = query.order_by(property_repository.Property.created_at.desc())
    query = query.offset(offset).limit(per_page)
    
    result = await db.execute(query)
    properties = result.scalars().all()
    
    # Формируем ответ
    items = []
    for prop in properties:
        photo_url = None
        if prop.photo_urls and isinstance(prop.photo_urls, list) and len(prop.photo_urls) > 0:
            photo_url = prop.photo_urls[0]
        
        items.append(PropertySummary(
            id=prop.id,
            title=prop.title[:100] if prop.title else "",  # Ограничиваем длину
            price=prop.price,
            currency=prop.currency or "RUB",
            rooms=prop.rooms,
            area=prop.area,
            floor=prop.floor,
            floors_total=prop.floors_total,
            district=prop.district,
            city=prop.city or "",
            property_type=prop.property_type or "",
            photo_url=photo_url,
        ))
    
    has_next = (offset + len(items)) < total
    next_cursor = str(page + 1) if has_next else None
    
    return PropertyListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        has_next=has_next,
        next_cursor=next_cursor,
    )


@router.get(
    "/properties/{property_id}",
    response_model=PropertyDetailMobile,
    summary="Детали объявления (мобильная версия)",
)
async def mobile_get_property(
    property_id: int,
    db: AsyncSession = Depends(get_db)
) -> PropertyDetailMobile:
    """
    Получение детальной информации об объявлении для мобильных клиентов.
    """
    prop = await property_repository.get_property(db, property_id)
    
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Объявление не найдено"
        )
    
    # Получаем фото
    photo_urls = []
    if prop.photo_urls and isinstance(prop.photo_urls, list):
        photo_urls = prop.photo_urls[:10]  # Ограничиваем до 10 фото
    
    return PropertyDetailMobile(
        id=prop.id,
        title=prop.title or "",
        description=prop.description,
        price=prop.price,
        currency=prop.currency or "RUB",
        rooms=prop.rooms,
        area=prop.area,
        floor=prop.floor,
        floors_total=prop.floors_total,
        district=prop.district,
        city=prop.city or "",
        address=prop.address,
        property_type=prop.property_type or "",
        photo_urls=photo_urls,
        source=prop.source,
        url=prop.url,
        created_at=prop.created_at,
        updated_at=prop.updated_at,
    )


# =============================================================================
# User Endpoints
# =============================================================================

@router.get(
    "/me",
    response_model=UserProfile,
    summary="Профиль текущего пользователя",
)
async def mobile_get_profile(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UserProfile:
    """
    Получение профиля текущего пользователя.
    """
    user = await user_repository.get_user_by_id(db, current_user.user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return UserProfile(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role.value if hasattr(user.role, 'value') else str(user.role),
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


@router.get(
    "/bookmarks",
    response_model=BookmarkListResponse,
    summary="Закладки пользователя",
)
async def mobile_get_bookmarks(
    current_user: TokenData = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=5, le=50),
    db: AsyncSession = Depends(get_db)
) -> BookmarkListResponse:
    """
    Получение списка закладок пользователя.
    """
    from app.db.models.bookmark import Bookmark
    
    offset = (page - 1) * per_page
    
    # Получаем закладки
    query = select(Bookmark).where(Bookmark.user_id == current_user.user_id)
    
    # Считаем общее количество
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Получаем данные
    query = query.order_by(Bookmark.created_at.desc())
    query = query.offset(offset).limit(per_page)
    
    result = await db.execute(query)
    bookmarks = result.scalars().all()
    
    items = [
        BookmarkMobile(
            id=bm.id,
            property_id=bm.property_id,
            created_at=bm.created_at,
        )
        for bm in bookmarks
    ]
    
    return BookmarkListResponse(
        items=items,
        total=total,
    )


# =============================================================================
# Health Check (Lightweight)
# =============================================================================

@router.get(
    "/health",
    summary="Проверка здоровья API",
)
async def mobile_health_check() -> dict:
    """
    Быстрая проверка здоровья для мобильных клиентов.
    """
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
    }
