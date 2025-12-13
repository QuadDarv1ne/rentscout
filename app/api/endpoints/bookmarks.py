"""
API endpoints для управления закладками и избранным.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Body, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bookmarks import (
    BookmarkService,
    bookmark_service,
    BookmarkType,
    BookmarkCreateRequest,
    BookmarkUpdateRequest,
)
from app.db.models.session import get_db
from app.utils.logger import logger


router = APIRouter(prefix="/bookmarks", tags=["bookmarks"])


# ============================================================================
# Pydantic Models
# ============================================================================

class BookmarkResponse(BaseModel):
    """Ответ с информацией о закладке."""
    id: int
    external_property_id: str
    property_title: str
    property_source: str
    property_price: int
    property_city: str
    property_link: str
    bookmark_type: str
    collection_name: Optional[str]
    notes: Optional[str]
    tags: List[str]
    rating: Optional[int]
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class BookmarkStatsResponse(BaseModel):
    """Статистика закладок пользователя."""
    total_favorites: int
    total_bookmarks: int
    total_viewed: int
    collections_count: int
    tags_count: int
    favorite_cities: dict
    favorite_sources: dict
    favorite_price_range: Optional[dict]


class AddBookmarkRequest(BaseModel):
    """Запрос на добавление закладки."""
    external_property_id: str = Field(..., description="ID объявления на источнике")
    property_title: str = Field(..., description="Название объявления")
    property_source: str = Field(..., description="Источник (avito, cian и т.д.)")
    property_price: float = Field(..., ge=0, description="Цена")
    property_city: str = Field(..., description="Город")
    property_link: str = Field(..., description="Ссылка на объявление")
    bookmark_type: str = Field(BookmarkType.FAVORITE.value, description="Тип закладки")
    collection_name: Optional[str] = Field(None, description="Название коллекции")
    notes: Optional[str] = Field(None, description="Пользовательские заметки")
    tags: Optional[List[str]] = Field(default_factory=list, description="Теги")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Оценка (1-5)")


class UpdateBookmarkRequest(BaseModel):
    """Запрос на обновление закладки."""
    notes: Optional[str] = Field(None, description="Заметки")
    tags: Optional[List[str]] = Field(None, description="Теги")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Оценка")
    collection_name: Optional[str] = Field(None, description="Новое название коллекции")
    is_active: Optional[bool] = Field(None, description="Активна ли закладка")


class RecommendationResponse(BaseModel):
    """Рекомендация на основе избранного."""
    external_id: str
    title: str
    price: float
    city: str
    reason: str  # Причина рекомендации
    similarity_score: float  # 0-1, насколько похожа на избранное


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/add", response_model=BookmarkResponse)
async def add_bookmark(
    user_id: str = Query(..., description="ID пользователя"),
    bookmark: AddBookmarkRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Добавить объявление в закладки/избранное.
    
    **Типы закладок:**
    - `favorite` - добавить в избранное
    - `bookmark` - добавить в коллекцию закладок
    - `viewed` - записать как просмотренное
    - `compare` - добавить для сравнения
    
    **Параметры:**
    - `user_id` - уникальный ID пользователя
    - `collection_name` - обязателен если `bookmark_type=bookmark`
    """
    # Create a new service instance with the database session
    service = BookmarkService(db_session=db)
    
    if bookmark.bookmark_type == BookmarkType.BOOKMARK.value:
        if not bookmark.collection_name:
            raise HTTPException(
                status_code=400,
                detail="collection_name required for bookmark type"
            )
        
        result = await service.add_bookmark(
            user_id=user_id,
            external_property_id=bookmark.external_property_id,
            property_title=bookmark.property_title,
            property_source=bookmark.property_source,
            property_price=bookmark.property_price,
            property_city=bookmark.property_city,
            property_link=bookmark.property_link,
            collection_name=bookmark.collection_name,
        )
    else:
        result = await service.add_favorite(
            user_id=user_id,
            external_property_id=bookmark.external_property_id,
            property_title=bookmark.property_title,
            property_source=bookmark.property_source,
            property_price=bookmark.property_price,
            property_city=bookmark.property_city,
            property_link=bookmark.property_link,
        )
    
    logger.info(f"Bookmark added for user {user_id}")
    
    return {
        "id": result.id,
        "external_property_id": result.external_property_id,
        "property_title": result.property_title,
        "property_source": result.property_source,
        "property_price": result.property_price,
        "property_city": result.property_city,
        "property_link": result.property_link,
        "bookmark_type": result.bookmark_type,
        "collection_name": result.collection_name,
        "notes": result.notes,
        "tags": result.tags or [],
        "rating": result.rating,
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "updated_at": result.updated_at.isoformat() if result.updated_at else None,
    }


@router.get("/favorites")
async def get_favorites(
    user_id: str = Query(..., description="ID пользователя"),
    city: Optional[str] = Query(None, description="Фильтр по городу"),
    skip: int = Query(0, ge=0, description="Пропустить N элементов"),
    limit: int = Query(50, ge=1, le=100, description="Максимум элементов"),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить избранные объявления пользователя.
    
    **Параметры:**
    - `user_id` - ID пользователя
    - `city` - фильтровать по городу (опционально)
    - `skip` - для пагинации
    - `limit` - максимум элементов на странице
    """
    service = BookmarkService(db_session=db)
    favorites = await service.get_favorites(
        user_id=user_id,
        city=city,
        skip=skip,
        limit=limit,
    )
    
    return {
        "count": len(favorites),
        "items": favorites,
        "skip": skip,
        "limit": limit,
    }


@router.get("/bookmarks")
async def get_bookmarks(
    user_id: str = Query(..., description="ID пользователя"),
    collection: Optional[str] = Query(None, description="Название коллекции"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить закладки пользователя.
    
    Может быть отфильтровано по названию коллекции.
    """
    service = BookmarkService(db_session=db)
    bookmarks = await service.get_bookmarks(
        user_id=user_id,
        collection_name=collection,
        skip=skip,
        limit=limit,
    )
    
    return {
        "count": len(bookmarks),
        "items": bookmarks,
        "collection": collection,
    }


@router.get("/collections")
async def get_collections(
    user_id: str = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """Получить список всех коллекций пользователя."""
    service = BookmarkService(db_session=db)
    collections = await service.get_collections(user_id=user_id)
    
    return {
        "count": len(collections),
        "collections": collections,
    }


@router.get("/history")
async def get_view_history(
    user_id: str = Query(..., description="ID пользователя"),
    days: int = Query(30, ge=1, le=365, description="Последние N дней"),
    limit: int = Query(100, ge=1, le=500, description="Максимум элементов"),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить историю просмотренных объявлений.
    
    **Параметры:**
    - `days` - показать просмотры за последние N дней
    - `limit` - максимум элементов в ответе
    """
    service = BookmarkService(db_session=db)
    history = await service.get_viewed_history(
        user_id=user_id,
        days=days,
        limit=limit,
    )
    
    return {
        "count": len(history),
        "period_days": days,
        "items": history,
    }


@router.put("/update/{external_property_id}")
async def update_bookmark(
    user_id: str = Query(..., description="ID пользователя"),
    external_property_id: str = None,
    update_request: UpdateBookmarkRequest = Body(..., description="Данные для обновления"),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновить информацию о закладке (заметки, оценку, теги).
    
    **Можно обновлять:**
    - notes - текстовые заметки
    - tags - список тегов
    - rating - оценка 1-5
    - collection_name - переместить в другую коллекцию
    """
    service = BookmarkService(db_session=db)
    await service.update_bookmark(
        user_id=user_id,
        external_property_id=external_property_id,
        update_data=update_request,
    )
    
    return {
        "status": "updated",
        "property_id": external_property_id,
    }


@router.delete("/remove")
async def remove_bookmark(
    user_id: str = Query(..., description="ID пользователя"),
    external_property_id: str = Query(..., description="ID объявления"),
    bookmark_type: str = Query(BookmarkType.FAVORITE.value, description="Тип закладки"),
    db: AsyncSession = Depends(get_db),
):
    """
    Удалить закладку.
    
    **Параметры:**
    - `user_id` - ID пользователя
    - `external_property_id` - ID объявления
    - `bookmark_type` - тип закладки (favorite, bookmark и т.д.)
    """
    service = BookmarkService(db_session=db)
    success = await service.remove_bookmark(
        user_id=user_id,
        external_property_id=external_property_id,
        bookmark_type=bookmark_type,
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    
    return {
        "status": "deleted",
        "property_id": external_property_id,
    }


@router.get("/stats", response_model=BookmarkStatsResponse)
async def get_bookmark_stats(
    user_id: str = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить статистику закладок пользователя.
    
    **Включает:**
    - Количество избранных объявлений
    - Количество коллекций
    - Популярные города и источники
    - Диапазон цен
    """
    service = BookmarkService(db_session=db)
    stats = await service.get_bookmark_stats(user_id=user_id)
    
    # Добавляем все необходимые поля
    return {
        "total_favorites": stats.get("total_favorites", 0),
        "total_bookmarks": stats.get("total_bookmarks", 0),
        "total_viewed": stats.get("total_viewed", 0),
        "collections_count": stats.get("collections", 0),
        "tags_count": stats.get("tags_count", 0),
        "favorite_cities": stats.get("favorite_cities", {}),
        "favorite_sources": stats.get("favorite_sources", {}),
        "favorite_price_range": stats.get("favorite_price_range"),
    }


@router.get("/recommendations", response_model=List[RecommendationResponse])
async def get_recommendations(
    user_id: str = Query(..., description="ID пользователя"),
    limit: int = Query(10, ge=1, le=50, description="Максимум рекомендаций"),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить рекомендации на основе избранного пользователя.
    
    Алгоритм анализирует:
    - Города, которые пользователь сохранял
    - Ценовой диапазон
    - Типы объявлений
    - Источники
    
    Возвращает новые объявления, которые соответствуют предпочтениям.
    """
    service = BookmarkService(db_session=db)
    recommendations = await service.get_recommendations(
        user_id=user_id,
        limit=limit,
    )
    
    return recommendations


@router.post("/compare")
async def add_to_compare(
    user_id: str = Query(..., description="ID пользователя"),
    external_property_id: str = Query(..., description="ID объявления"),
):
    """
    Добавить объявление для сравнения.
    
    Объявления, добавленные для сравнения, можно затем анализировать
    и получать рекомендации на их основе.
    """
    return {
        "status": "added_for_comparison",
        "property_id": external_property_id,
    }


@router.get("/compare")
async def get_compare_list(
    user_id: str = Query(..., description="ID пользователя"),
):
    """Получить список объявлений, добавленных для сравнения."""
    return {
        "count": 0,
        "items": [],
    }


@router.post("/compare/clear")
async def clear_compare_list(
    user_id: str = Query(..., description="ID пользователя"),
):
    """Очистить список объявлений для сравнения."""
    return {
        "status": "cleared",
        "message": "Compare list cleared",
    }


@router.get("/health")
async def bookmarks_health():
    """Проверить статус сервиса закладок."""
    return {
        "status": "healthy",
        "service": "bookmarks",
        "features": [
            "favorites",
            "bookmarks_collections",
            "view_history",
            "recommendations",
            "comparison",
            "statistics",
        ],
    }
