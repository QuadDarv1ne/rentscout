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
from sqlalchemy import JSON

from app.db.models.property import Base
from app.utils.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, func, desc, text
from datetime import datetime, timedelta


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
    property_data = Column(JSON, nullable=True)  # Полные данные объявления при добавлении
    
    bookmark_type = Column(String(50), default=BookmarkType.FAVORITE.value, index=True)
    collection_name = Column(String(255), nullable=True, index=True)
    
    notes = Column(Text, nullable=True)  # Пользовательские заметки
    tags = Column(JSON, default=list)  # Теги для категоризации
    
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
    
    favorite_cities = Column(JSON, default=dict)  # {city: count}
    favorite_sources = Column(JSON, default=dict)  # {source: count}
    favorite_price_range = Column(JSON, nullable=True)  # {min: X, max: Y, avg: Z}
    
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
        self.db: AsyncSession = db_session
    
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
            try:
                stmt = delete(UserBookmark).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.external_property_id == external_property_id,
                        UserBookmark.bookmark_type == bookmark_type
                    )
                )
                result = await self.db.execute(stmt)
                await self.db.commit()
                deleted_count = result.rowcount
                logger.info(f"Removed {deleted_count} bookmark(s): {external_property_id} for user {user_id}")
                return deleted_count > 0
            except Exception as e:
                await self.db.rollback()
                logger.error(f"Error removing bookmark: {e}")
                return False
        
        return False
    
    async def get_favorites(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 50,
        city: Optional[str] = None,
    ) -> List[UserBookmark]:
        """Получить избранные объявления пользователя."""
        if self.db:
            try:
                query = select(UserBookmark).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.FAVORITE.value,
                        UserBookmark.is_active == True
                    )
                ).order_by(desc(UserBookmark.created_at)).offset(skip).limit(limit)
                
                if city:
                    query = query.where(UserBookmark.property_city == city)
                
                result = await self.db.execute(query)
                bookmarks = result.scalars().all()
                logger.info(f"Fetched {len(bookmarks)} favorites for user {user_id}")
                return list(bookmarks)
            except Exception as e:
                logger.error(f"Error fetching favorites for user {user_id}: {e}")
                return []
        
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
        if self.db:
            try:
                query = select(UserBookmark).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.BOOKMARK.value,
                        UserBookmark.is_active == True
                    )
                ).order_by(desc(UserBookmark.created_at)).offset(skip).limit(limit)
                
                if collection_name:
                    query = query.where(UserBookmark.collection_name == collection_name)
                
                result = await self.db.execute(query)
                bookmarks = result.scalars().all()
                logger.info(f"Fetched {len(bookmarks)} bookmarks for user {user_id}")
                return list(bookmarks)
            except Exception as e:
                logger.error(f"Error fetching bookmarks for user {user_id}: {e}")
                return []
        
        logger.info(f"Fetching bookmarks for user {user_id}")
        return []
    
    async def get_collections(self, user_id: str) -> List[str]:
        """Получить список коллекций пользователя."""
        if self.db:
            try:
                query = select(UserBookmark.collection_name).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.BOOKMARK.value,
                        UserBookmark.is_active == True,
                        UserBookmark.collection_name.isnot(None)
                    )
                ).distinct()
                
                result = await self.db.execute(query)
                collections = [row[0] for row in result.fetchall()]
                logger.info(f"Fetched {len(collections)} collections for user {user_id}")
                return collections
            except Exception as e:
                logger.error(f"Error fetching collections for user {user_id}: {e}")
                return []
        
        logger.info(f"Fetching collections for user {user_id}")
        return []
    
    async def get_viewed_history(
        self,
        user_id: str,
        days: int = 30,
        limit: int = 100,
    ) -> List[UserBookmark]:
        """Получить историю просмотренных объявлений."""
        if self.db:
            try:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                query = select(UserBookmark).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.VIEWED.value,
                        UserBookmark.created_at >= cutoff_date
                    )
                ).order_by(desc(UserBookmark.last_viewed_at)).limit(limit)
                
                result = await self.db.execute(query)
                bookmarks = result.scalars().all()
                logger.info(f"Fetched {len(bookmarks)} viewed items for user {user_id}")
                return list(bookmarks)
            except Exception as e:
                logger.error(f"Error fetching view history for user {user_id}: {e}")
                return []
        
        logger.info(f"Fetching view history for user {user_id} (last {days} days)")
        return []
    
    async def update_bookmark(
        self,
        user_id: str,
        external_property_id: str,
        update_data: BookmarkUpdateRequest,
    ) -> Optional[UserBookmark]:
        """Обновить закладку."""
        if self.db:
            try:
                # Build update values
                update_values = {}
                if update_data.notes is not None:
                    update_values['notes'] = update_data.notes
                if update_data.tags is not None:
                    update_values['tags'] = update_data.tags
                if update_data.rating is not None:
                    update_values['rating'] = update_data.rating
                if update_data.collection_name is not None:
                    update_values['collection_name'] = update_data.collection_name
                if update_data.is_active is not None:
                    update_values['is_active'] = update_data.is_active
                
                if update_values:
                    update_values['updated_at'] = datetime.utcnow()
                    
                    stmt = update(UserBookmark).where(
                        and_(
                            UserBookmark.user_id == user_id,
                            UserBookmark.external_property_id == external_property_id
                        )
                    ).values(**update_values)
                    
                    await self.db.execute(stmt)
                    await self.db.commit()
                
                # Fetch updated bookmark
                query = select(UserBookmark).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.external_property_id == external_property_id
                    )
                )
                result = await self.db.execute(query)
                updated_bookmark = result.scalar_one_or_none()
                
                logger.info(f"Updated bookmark: {external_property_id} for user {user_id}")
                return updated_bookmark
            except Exception as e:
                await self.db.rollback()
                logger.error(f"Error updating bookmark: {e}")
                return None
        
        logger.info(f"Updating bookmark: {external_property_id} for user {user_id}")
        return None
    
    async def get_bookmark_stats(self, user_id: str) -> Dict[str, Any]:
        """Получить статистику закладок пользователя."""
        if self.db:
            try:
                stats = {
                    "total_favorites": 0,
                    "total_bookmarks": 0,
                    "total_viewed": 0,
                    "collections": 0,
                    "favorite_cities": {},
                    "favorite_sources": {},
                    "favorite_price_range": None,
                    "tags_count": 0,
                }
                
                # Get counts by type
                fav_query = select(func.count()).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.FAVORITE.value,
                        UserBookmark.is_active == True
                    )
                )
                bookmark_query = select(func.count()).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.BOOKMARK.value,
                        UserBookmark.is_active == True
                    )
                )
                viewed_query = select(func.count()).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.VIEWED.value
                    )
                )
                
                fav_result = await self.db.execute(fav_query)
                bookmark_result = await self.db.execute(bookmark_query)
                viewed_result = await self.db.execute(viewed_query)
                
                stats["total_favorites"] = fav_result.scalar_one()
                stats["total_bookmarks"] = bookmark_result.scalar_one()
                stats["total_viewed"] = viewed_result.scalar_one()
                
                # Get collections count
                collections_query = select(func.count(func.distinct(UserBookmark.collection_name))).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.BOOKMARK.value,
                        UserBookmark.is_active == True,
                        UserBookmark.collection_name.isnot(None)
                    )
                )
                collections_result = await self.db.execute(collections_query)
                stats["collections"] = collections_result.scalar_one()
                
                # Get favorite cities
                city_query = select(
                    UserBookmark.property_city, 
                    func.count(UserBookmark.id).label('count')
                ).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.FAVORITE.value,
                        UserBookmark.is_active == True,
                        UserBookmark.property_city.isnot(None)
                    )
                ).group_by(UserBookmark.property_city).order_by(desc('count')).limit(10)
                
                city_result = await self.db.execute(city_query)
                stats["favorite_cities"] = {row[0]: row[1] for row in city_result.fetchall()}
                
                # Get favorite sources
                source_query = select(
                    UserBookmark.property_source, 
                    func.count(UserBookmark.id).label('count')
                ).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.FAVORITE.value,
                        UserBookmark.is_active == True,
                        UserBookmark.property_source.isnot(None)
                    )
                ).group_by(UserBookmark.property_source).order_by(desc('count'))
                
                source_result = await self.db.execute(source_query)
                stats["favorite_sources"] = {row[0]: row[1] for row in source_result.fetchall()}
                
                # Get price range for favorites
                price_query = select(
                    func.min(UserBookmark.property_price),
                    func.max(UserBookmark.property_price),
                    func.avg(UserBookmark.property_price)
                ).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.FAVORITE.value,
                        UserBookmark.is_active == True,
                        UserBookmark.property_price.isnot(None)
                    )
                )
                
                price_result = await self.db.execute(price_query)
                price_row = price_result.fetchone()
                if price_row and price_row[0] is not None:
                    stats["favorite_price_range"] = {
                        "min": float(price_row[0]),
                        "max": float(price_row[1]),
                        "avg": float(price_row[2])
                    }
                
                # Get tags count
                tags_query = select(UserBookmark.tags).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.is_active == True,
                        UserBookmark.tags.isnot(None)
                    )
                )
                
                tags_result = await self.db.execute(tags_query)
                all_tags = []
                for row in tags_result.fetchall():
                    if row[0]:
                        all_tags.extend(row[0])
                stats["tags_count"] = len(set(all_tags))
                
                logger.info(f"Retrieved bookmark stats for user {user_id}")
                return stats
            except Exception as e:
                logger.error(f"Error getting bookmark stats for user {user_id}: {e}")
                return {
                    "total_favorites": 0,
                    "total_bookmarks": 0,
                    "total_viewed": 0,
                    "collections": 0,
                    "favorite_cities": {},
                    "favorite_sources": {},
                    "favorite_price_range": None,
                    "tags_count": 0,
                }
        
        stats = {
            "total_favorites": 0,
            "total_bookmarks": 0,
            "total_viewed": 0,
            "collections": 0,
            "favorite_cities": {},
            "favorite_sources": {},
            "favorite_price_range": None,
            "tags_count": 0,
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
        if self.db:
            try:
                # Get user's favorite cities and price range
                fav_query = select(
                    UserBookmark.property_city,
                    UserBookmark.property_price
                ).where(
                    and_(
                        UserBookmark.user_id == user_id,
                        UserBookmark.bookmark_type == BookmarkType.FAVORITE.value,
                        UserBookmark.is_active == True
                    )
                )
                
                fav_result = await self.db.execute(fav_query)
                fav_rows = fav_result.fetchall()
                
                if not fav_rows:
                    logger.info(f"No favorites found for user {user_id}, returning empty recommendations")
                    return []
                
                # Extract cities and prices
                cities = [row[0] for row in fav_rows if row[0]]
                prices = [float(row[1]) for row in fav_rows if row[1] is not None]
                
                if not cities:
                    logger.info(f"No cities found in favorites for user {user_id}")
                    return []
                
                # Calculate price range (with some buffer)
                min_price = min(prices) * 0.8 if prices else 0
                max_price = max(prices) * 1.2 if prices else float('inf')
                
                # Get most common city
                city_counts = {}
                for city in cities:
                    city_counts[city] = city_counts.get(city, 0) + 1
                preferred_city = max(city_counts, key=city_counts.get)
                
                # Simple recommendation: find properties in the same city with similar price range
                # In a real implementation, this would be much more sophisticated
                recommendations = [
                    {
                        "external_id": f"rec_{i}",
                        "title": f"Рекомендуемое объявление в {preferred_city}",
                        "price": min_price + (max_price - min_price) * (i / 10),
                        "city": preferred_city,
                        "reason": f"Похоже на ваши избранные объявления в {preferred_city}",
                        "similarity_score": 0.8 - (i * 0.05)
                    }
                    for i in range(min(limit, 5))
                ]
                
                logger.info(f"Generated {len(recommendations)} recommendations for user {user_id}")
                return recommendations
            except Exception as e:
                logger.error(f"Error generating recommendations for user {user_id}: {e}")
                return []
        
        logger.info(f"Generating recommendations for user {user_id}")
        return []


# Глобальный экземпляр сервиса
bookmark_service = BookmarkService()
