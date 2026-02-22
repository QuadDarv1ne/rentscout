"""
Типизированные CRUD операции для Property.

Использование:
    from app.db.typed_crud import PropertyCRUD
    
    # Использование
    result = await PropertyCRUD.create(db, property_data)
    properties = await PropertyCRUD.get_all(db, limit=100)
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import select, update, delete, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.db.models.property import Property, PropertyPriceHistory, PropertyView
from app.models.schemas import PropertyCreate
from app.schemas.db_responses import (
    PropertyResponse,
    PropertiesListResponse,
    PaginatedResponse,
    BulkUpsertResponse,
    PropertyStatistics,
)
from app.utils.metrics import metrics_collector

logger = logging.getLogger(__name__)


class PropertyCRUD:
    """Типизированные CRUD операции для Property."""

    @staticmethod
    async def create(
        db: AsyncSession,
        property_data: PropertyCreate
    ) -> PropertyResponse:
        """
        Создает новый объект недвижимости.

        Args:
            db: Сессия базы данных
            property_data: Данные для создания

        Returns:
            PropertyResponse с данными созданного объекта
        """
        start_time = time.time()

        # Extract location fields
        location = property_data.location or {}
        property_dict = property_data.model_dump()

        db_property = Property(
            source=property_dict["source"],
            external_id=property_dict["external_id"],
            title=property_dict["title"],
            description=property_dict.get("description"),
            link=property_dict.get("link"),
            price=property_dict["price"],
            rooms=property_dict.get("rooms"),
            area=property_dict.get("area"),
            city=location.get("city"),
            district=location.get("district"),
            address=location.get("address"),
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            location=location,
            photos=property_dict.get("photos", []),
        )

        db.add(db_property)
        await db.flush()
        await db.refresh(db_property)

        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("INSERT", "properties", duration)
        metrics_collector.record_property_saved()

        logger.info(f"Created property: {db_property.id} from {db_property.source}")
        return PropertyResponse.model_validate(db_property)

    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        property_id: int,
        include_photos: bool = True
    ) -> Optional[PropertyResponse]:
        """
        Получает объект недвижимости по ID.

        Args:
            db: Сессия базы данных
            property_id: ID объекта
            include_photos: Загружать ли фото (для future expansion)

        Returns:
            PropertyResponse или None если не найден
        """
        start_time = time.time()

        query = select(Property).where(Property.id == property_id)

        # Eager loading для оптимизации (N+1 fix)
        if include_photos:
            query = query.options(selectinload(Property.photos))

        result = await db.execute(query)
        db_property = result.scalar_one_or_none()

        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("SELECT", "properties", duration)

        if db_property is None:
            return None

        return PropertyResponse.model_validate(db_property)

    @staticmethod
    async def get_all(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = True
    ) -> PropertiesListResponse:
        """
        Получает список объектов недвижимости.

        Args:
            db: Сессия базы данных
            skip: Количество пропускаемых записей
            limit: Максимальное количество записей
            is_active: Фильтр по активности

        Returns:
            PropertiesListResponse с пагинацией
        """
        start_time = time.time()

        # Build query
        query = select(Property)
        if is_active is not None:
            query = query.where(Property.is_active == is_active)

        # Count total
        count_query = select(func.count(Property.id))
        if is_active is not None:
            count_query = count_query.where(Property.is_active == is_active)

        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.offset(skip).limit(limit).order_by(desc(Property.created_at))

        result = await db.execute(query)
        properties = result.scalars().all()

        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("SELECT", "properties", duration)

        # Create paginated response
        response = PaginatedResponse.create(
            items=[PropertyResponse.model_validate(p) for p in properties],
            total=total,
            skip=skip,
            limit=limit,
        )

        return PropertiesListResponse.model_validate(response)

    @staticmethod
    async def update(
        db: AsyncSession,
        property_id: int,
        update_data: Dict[str, Any]
    ) -> Optional[PropertyResponse]:
        """
        Обновляет объект недвижимости.

        Args:
            db: Сессия базы данных
            property_id: ID объекта
            update_data: Данные для обновления

        Returns:
            PropertyResponse с обновленными данными или None
        """
        start_time = time.time()

        # Check if property exists
        existing = await PropertyCRUD.get_by_id(db, property_id)
        if existing is None:
            return None

        # Update
        update_stmt = (
            update(Property)
            .where(Property.id == property_id)
            .values(**update_data, last_updated=datetime.utcnow())
            .returning(Property)
        )

        result = await db.execute(update_stmt)
        db_property = result.scalar_one()
        await db.commit()

        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("UPDATE", "properties", duration)

        logger.info(f"Updated property: {property_id}")
        return PropertyResponse.model_validate(db_property)

    @staticmethod
    async def delete(
        db: AsyncSession,
        property_id: int
    ) -> bool:
        """
        Удаляет объект недвижимости.

        Args:
            db: Сессия базы данных
            property_id: ID объекта

        Returns:
            True если удален, False если не найден
        """
        start_time = time.time()

        delete_stmt = delete(Property).where(Property.id == property_id)
        result = await db.execute(delete_stmt)
        await db.commit()

        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("DELETE", "properties", duration)

        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted property: {property_id}")

        return deleted

    @staticmethod
    async def bulk_upsert(
        db: AsyncSession,
        properties_data: List[PropertyCreate]
    ) -> BulkUpsertResponse:
        """
        Массовая операция upsert (insert or update).

        Args:
            db: Сессия базы данных
            properties_data: Список данных для вставки/обновления

        Returns:
            BulkUpsertResponse с результатами операции
        """
        start_time = time.time()

        if not properties_data:
            return BulkUpsertResponse(success=True, processing_time_ms=0)

        try:
            # Convert to dicts
            properties_dicts = []
            for prop_data in properties_data:
                location = prop_data.location or {}
                prop_dict = prop_data.model_dump()

                properties_dicts.append({
                    "source": prop_dict["source"],
                    "external_id": prop_dict["external_id"],
                    "title": prop_dict["title"],
                    "description": prop_dict.get("description"),
                    "link": prop_dict.get("link"),
                    "price": prop_dict["price"],
                    "rooms": prop_dict.get("rooms"),
                    "area": prop_dict.get("area"),
                    "city": location.get("city"),
                    "district": location.get("district"),
                    "address": location.get("address"),
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "location": location,
                    "photos": prop_dict.get("photos", []),
                    "last_seen": datetime.utcnow(),
                    "is_active": True,
                })

            # PostgreSQL UPSERT
            stmt = insert(Property).values(properties_dicts)
            stmt = stmt.on_conflict_do_update(
                index_elements=["source", "external_id"],
                set_={
                    "price": stmt.excluded.price,
                    "last_seen": datetime.utcnow(),
                    "is_active": True,
                }
            )
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["source", "external_id"]
            )

            await db.execute(stmt)
            await db.commit()

            duration = time.time() - start_time
            metrics_collector.record_db_query("BULK_UPSERT", "properties", duration)

            logger.info(f"Bulk upserted {len(properties_data)} properties in {duration:.2f}s")

            return BulkUpsertResponse(
                success=True,
                created=len(properties_data),  # Approximation
                updated=0,
                errors=0,
                processing_time_ms=duration * 1000,
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Bulk upsert error: {e}", exc_info=True)

            return BulkUpsertResponse(
                success=False,
                errors=len(properties_data),
                error_details=[{"error": str(e)}],
                processing_time_ms=(time.time() - start_time) * 1000,
            )

    @staticmethod
    async def get_statistics(
        db: AsyncSession,
        city: Optional[str] = None,
        district: Optional[str] = None,
        days: int = 30
    ) -> PropertyStatistics:
        """
        Получает статистику по недвижимости.

        Args:
            db: Сессия базы данных
            city: Фильтр по городу
            district: Фильтр по району
            days: Период в днях

        Returns:
            PropertyStatistics со статистикой
        """
        start_time = time.time()

        # Build filters
        filters = [
            Property.is_active == True,
            Property.last_seen >= datetime.utcnow() - timedelta(days=days),
        ]
        if city:
            filters.append(Property.city == city)
        if district:
            filters.append(Property.district == district)

        # Query statistics
        result = await db.execute(
            select(
                func.count(Property.id).label("total"),
                func.avg(Property.price).label("avg_price"),
                func.min(Property.price).label("min_price"),
                func.max(Property.price).label("max_price"),
                func.avg(Property.area).label("avg_area"),
                func.min(Property.area).label("min_area"),
                func.max(Property.area).label("max_area"),
                func.avg(Property.rooms).label("avg_rooms"),
            ).where(and_(*filters))
        )

        row = result.first()

        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("STATS", "properties", duration)

        return PropertyStatistics(
            total=row.total or 0,
            avg_price=float(row.avg_price) if row.avg_price else None,
            min_price=float(row.min_price) if row.min_price else None,
            max_price=float(row.max_price) if row.max_price else None,
            avg_area=float(row.avg_area) if row.avg_area else None,
            min_area=float(row.min_area) if row.min_area else None,
            max_area=float(row.max_area) if row.max_area else None,
            avg_rooms=float(row.avg_rooms) if row.avg_rooms else None,
        )

    @staticmethod
    async def search(
        db: AsyncSession,
        city: str,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_rooms: Optional[int] = None,
        max_rooms: Optional[int] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        skip: int = 0,
        limit: int = 100
    ) -> PropertiesListResponse:
        """
        Поиск объектов недвижимости с фильтрами.

        Args:
            db: Сессия базы данных
            city: Город
            min_price: Минимальная цена
            max_price: Максимальная цена
            min_rooms: Минимальное количество комнат
            max_rooms: Максимальное количество комнат
            min_area: Минимальная площадь
            max_area: Максимальная площадь
            skip: Количество пропускаемых записей
            limit: Максимальное количество записей

        Returns:
            PropertiesListResponse с результатами поиска
        """
        start_time = time.time()

        # Build filters
        filters = [
            Property.city == city,
            Property.is_active == True,
        ]

        if min_price is not None:
            filters.append(Property.price >= min_price)
        if max_price is not None:
            filters.append(Property.price <= max_price)
        if min_rooms is not None:
            filters.append(Property.rooms >= min_rooms)
        if max_rooms is not None:
            filters.append(Property.rooms <= max_rooms)
        if min_area is not None:
            filters.append(Property.area >= min_area)
        if max_area is not None:
            filters.append(Property.area <= max_area)

        # Count total
        count_query = select(func.count(Property.id)).where(and_(*filters))
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Get results
        query = (
            select(Property)
            .where(and_(*filters))
            .offset(skip)
            .limit(limit)
            .order_by(desc(Property.last_seen))
        )

        result = await db.execute(query)
        properties = result.scalars().all()

        # Record metrics
        duration = time.time() - start_time
        metrics_collector.record_db_query("SEARCH", "properties", duration)

        # Create paginated response
        response = PaginatedResponse.create(
            items=[PropertyResponse.model_validate(p) for p in properties],
            total=total,
            skip=skip,
            limit=limit,
        )

        return PropertiesListResponse.model_validate(response)


__all__ = ["PropertyCRUD"]
