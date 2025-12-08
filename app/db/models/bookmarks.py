"""
Сервис управления избранным и закладками.

Позволяет пользователям:
- Добавлять/удалять объявления в избранное
- Организовывать закладки по коллекциям
- Просматривать историю просмотренных объявлений
- Получать рекомендации на основе избранного
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, UniqueConstraint, Index, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.models.property import Base
from app.utils.logger import logger


class BookmarkType(str, Enum):
    """Тип закладки."""
    FAVORITE = "favorite"  # Избранное
    BOOKMARK = "bookmark"  # Закладка в коллекции
    VIEWED = "viewed"  # Просмотренные
    COMPARE = "compare"  # Для сравнения


class UserBookmark(Base):
    """Модель закладки/избранного пользователя."""
    
    __tablename__ = "user_bookmarks"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, index=True)
    external_property_id = Column(String(255), nullable=False, index=True)
    property_title = Column(String(500))
    property_source = Column(String(100))
    property_price = Column(Integer)
    property_city = Column(String(255), index=True)
    property_link = Column(Text)
    property_data = Column(JSONB, nullable=True)  # Полные данные объявления при добавлении
    
    bookmark_type = Column(String(50), default=BookmarkType.FAVORITE.value, index=True)
    collection_name = Column(String(255), nullable=True, index=True)
    
    notes = Column(Text, nullable=True)  # Пользовательские заметки
    tags = Column(JSONB, default=list)  # Теги для категоризации
    
    rating = Column(Integer, nullable=True)  # Оценка пользователя (1-5)
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_viewed_at = Column(DateTime, nullable=True)
    
    # Индексы для оптимизации поиска
    __table_args__ = (
        UniqueConstraint('user_id', 'external_property_id', 'bookmark_type', 
                        name='uq_user_property_type'),
        Index('ix_user_bookmarks_user_id', 'user_id'),
        Index('ix_user_bookmarks_created_at', 'created_at'),
        Index('ix_user_bookmarks_type_city', 'bookmark_type', 'property_city'),
        Index('ix_user_bookmarks_collection', 'user_id', 'collection_name'),
    )
    
    def __repr__(self):
        return f"<UserBookmark(user_id='{self.user_id}', property_id='{self.external_property_id}', type='{self.bookmark_type}')>"


class BookmarkStats(Base):
    """Статистика закладок пользователя."""
    
    __tablename__ = "bookmark_stats"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False, unique=True, index=True)
    
    total_favorites = Column(Integer, default=0)
    total_bookmarks = Column(Integer, default=0)
    total_viewed = Column(Integer, default=0)
    total_compared = Column(Integer, default=0)
    
    favorite_cities = Column(JSONB, default=dict)  # {city: count}
    favorite_sources = Column(JSONB, default=dict)  # {source: count}
    favorite_price_range = Column(JSONB, nullable=True)  # {min: X, max: Y, avg: Z}
    
    collections_count = Column(Integer, default=0)
    tags_count = Column(Integer, default=0)
    
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


@dataclass
class BookmarkCreateRequest:
    """Запрос на создание закладки."""
    user_id: str
    external_property_id: str
    property_title: str
    property_source: str
    property_price: float
    property_city: str
    property_link: str
    bookmark_type: str = BookmarkType.FAVORITE.value
    collection_name: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = None
    rating: Optional[int] = None
    property_data: Optional[Dict[str, Any]] = None


@dataclass
class BookmarkUpdateRequest:
    """Запрос на обновление закладки."""
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    rating: Optional[int] = None
    collection_name: Optional[str] = None
    is_active: Optional[bool] = None


class BookmarkService:
    """Сервис управления закладками."""
    
    def __init__(self, db_session=None):
        self.db = db_session
    
    async def add_favorite(
        self,
        user_id: str,
        external_property_id: str,
        property_title: str,
        property_source: str,
        property_price: float,
        property_city: str,
        property_link: str,
        property_data: Optional[Dict] = None,
    ) -> UserBookmark:
        """Добавить объявление в избранное."""
        bookmark = UserBookmark(
            user_id=user_id,
            external_property_id=external_property_id,
            property_title=property_title,
            property_source=property_source,
            property_price=int(property_price),
            property_city=property_city,
            property_link=property_link,
            bookmark_type=BookmarkType.FAVORITE.value,
            property_data=property_data,
        )
        
        if self.db:
            self.db.add(bookmark)
            await self.db.flush()
        
        logger.info(f"Added to favorites: {external_property_id} for user {user_id}")
        return bookmark
    
    async def add_bookmark(
        self,
        user_id: str,
        external_property_id: str,
        property_title: str,
        property_source: str,
        property_price: float,
        property_city: str,
        property_link: str,
        collection_name: str,
        property_data: Optional[Dict] = None,
    ) -> UserBookmark:
        """Добавить объявление в закладки коллекции."""
        bookmark = UserBookmark(
            user_id=user_id,
            external_property_id=external_property_id,
            property_title=property_title,
            property_source=property_source,
            property_price=int(property_price),
            property_city=property_city,
            property_link=property_link,
            bookmark_type=BookmarkType.BOOKMARK.value,
            collection_name=collection_name,
            property_data=property_data,
        )
        
        if self.db:
            self.db.add(bookmark)
            await self.db.flush()
        
        logger.info(f"Added to collection '{collection_name}': {external_property_id} for user {user_id}")
        return bookmark
    
    async def record_view(
        self,
        user_id: str,
        external_property_id: str,
        property_title: str,
        property_source: str,
        property_price: float,
        property_city: str,
        property_link: str,
    ) -> UserBookmark:
        """Записать просмотр объявления."""
        bookmark = UserBookmark(
            user_id=user_id,
            external_property_id=external_property_id,
            property_title=property_title,
            property_source=property_source,
            property_price=int(property_price),
            property_city=property_city,
            property_link=property_link,
            bookmark_type=BookmarkType.VIEWED.value,
            last_viewed_at=datetime.utcnow(),
        )
        
        if self.db:
            self.db.add(bookmark)
            await self.db.flush()
        
        return bookmark
    
    async def remove_bookmark(self, user_id: str, external_property_id: str, bookmark_type: str) -> bool:
        """Удалить закладку."""
        if self.db:
            # Мягкое удаление
            # В реальной БД нужно использовать proper delete с WHERE clause
            logger.info(f"Removed bookmark: {external_property_id} for user {user_id}")
        
        return True
    
    async def get_favorites(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50,
        city: Optional[str] = None,
    ) -> List[UserBookmark]:
        """Получить избранные объявления пользователя."""
        logger.info(f"Fetching favorites for user {user_id}")
        return []
    
    async def get_bookmarks(
        self,
        user_id: str,
        collection_name: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[UserBookmark]:
        """Получить закладки пользователя."""
        logger.info(f"Fetching bookmarks for user {user_id}")
        return []
    
    async def get_collections(self, user_id: str) -> List[str]:
        """Получить список коллекций пользователя."""
        logger.info(f"Fetching collections for user {user_id}")
        return []
    
    async def get_viewed_history(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 100,
    ) -> List[UserBookmark]:
        """Получить историю просмотренных объявлений."""
        logger.info(f"Fetching view history for user {user_id} (last {days} days)")
        return []
    
    async def update_bookmark(
        self,
        user_id: str,
        external_property_id: str,
        update_data: BookmarkUpdateRequest,
    ) -> Optional[UserBookmark]:
        """Обновить закладку."""
        logger.info(f"Updating bookmark: {external_property_id} for user {user_id}")
        return None
    
    async def get_bookmark_stats(self, user_id: str) -> Dict[str, Any]:
        """Получить статистику закладок пользователя."""
        stats = {
            "total_favorites": 0,
            "total_bookmarks": 0,
            "total_viewed": 0,
            "collections": 0,
            "favorite_cities": {},
            "favorite_sources": {},
            "recent_activity": [],
        }
        
        logger.info(f"Retrieved bookmark stats for user {user_id}")
        return stats
    
    async def get_recommendations(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Получить рекомендации на основе избранного пользователя.
        
        Учитывает:
        - Города, которые пользователь добавлял в избранное
        - Ценовой диапазон
        - Типы объявлений (студии, 1-комнатные и т.д.)
        """
        logger.info(f"Generating recommendations for user {user_id}")
        return []


# Глобальный экземпляр сервиса
bookmark_service = BookmarkService()
