"""
Оптимизированные batch операции для базы данных.

Использует:
- Asyncpg для асинхронных операций
- COPY для массовой загрузки данных
- ON CONFLICT для deduplication
- Connection pooling для эффективности
"""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from asyncpg import Connection, exceptions

from app.db.models.property import Property
from app.models.schemas import PropertyCreate
from app.utils.logger import logger
from app.utils.metrics import metrics_collector


class BatchPropertyInserter:
    """
    Оптимизированный batch insert для свойств.
    
    Особенности:
    - Использует COPY для быстрой загрузки
    - Автоматическая retry логика
    - Chunking для больших объёмов
    - Deduplication через ON CONFLICT
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        chunk_size: int = 1000,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Инициализация batch insert.
        
        Args:
            db_session: SQLAlchemy async сессия
            chunk_size: Размер чанка для batch операций
            max_retries: Максимум попыток при ошибке
            retry_delay: Задержка между попытками (сек)
        """
        self.db = db_session
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def insert_with_upsert(
        self,
        properties: List[PropertyCreate],
        conflict_columns: List[str] = None
    ) -> Tuple[int, int]:
        """
        Массовая вставка с обновлением при конфликте.
        
        Args:
            properties: Список свойств для вставки
            conflict_columns: Колонки для проверки конфликта
            
        Returns:
            Кортеж (вставлено, обновлено)
        """
        start_time = time.time()
        conflict_columns = conflict_columns or ['source', 'external_id']
        
        if not properties:
            return 0, 0
        
        total_inserted = 0
        total_updated = 0
        
        # Разбиваем на чанки для лучшей производительности
        chunks = self._chunkify(properties, self.chunk_size)
        
        for chunk in chunks:
            inserted, updated = await self._process_chunk(
                chunk,
                conflict_columns
            )
            total_inserted += inserted
            total_updated += updated
        
        duration = time.time() - start_time
        
        # Записываем метрики
        metrics_collector.record_db_query(
            "BULK_UPSERT",
            "properties",
            duration,
            rows_affected=total_inserted + total_updated
        )
        
        logger.info(
            f"Batch upsert completed: {total_inserted} inserted, "
            f"{total_updated} updated in {duration:.2f}s"
        )
        
        return total_inserted, total_updated
    
    async def _process_chunk(
        self,
        chunk: List[PropertyCreate],
        conflict_columns: List[str]
    ) -> Tuple[int, int]:
        """
        Обрабатывает чанк свойств с retry логикой.
        
        Args:
            chunk: Чанк свойств
            conflict_columns: Колонки для конфликта
            
        Returns:
            Кортеж (вставлено, обновлено)
        """
        for attempt in range(self.max_retries):
            try:
                return await self._insert_chunk(chunk, conflict_columns)
            
            except exceptions.PostgresError as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to insert chunk after {self.max_retries} attempts: {e}")
                    raise
                
                logger.warning(
                    f"Chunk insert failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                    f"Retrying in {self.retry_delay}s..."
                )
                await asyncio.sleep(self.retry_delay * (attempt + 1))
        
        return 0, 0  # Should not reach here
    
    async def _insert_chunk(
        self,
        chunk: List[PropertyCreate],
        conflict_columns: List[str]
    ) -> Tuple[int, int]:
        """
        Вставляет чанк свойств используя INSERT ... ON CONFLICT.
        
        Args:
            chunk: Чанк свойств
            conflict_columns: Колонки для проверки конфликта
            
        Returns:
            Кортеж (вставлено, обновлено)
        """
        # Конвертируем в словари
        properties_dicts = [self._prepare_property_dict(prop) for prop in chunk]
        
        # Создаём INSERT statement
        stmt = insert(Property).values(properties_dicts)
        
        # ON CONFLICT DO UPDATE для обновления существующих
        update_dict = {
            'price': stmt.excluded.price,
            'title': stmt.excluded.title,
            'description': stmt.excluded.description,
            'last_updated': datetime.utcnow(),
        }
        
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_=update_dict,
            where=(Property.price != stmt.excluded.price)  # Обновляем только если цена изменилась
        )
        
        # Выполняем вставку
        result = await self.db.execute(stmt)
        await self.db.flush()
        
        # Считаем вставленные и обновлённые строки
        # Примечание: PostgreSQL не возвращает точное количество в ON CONFLICT
        # Поэтому оцениваем по количеству записей в чанке
        inserted = len(chunk)
        updated = 0
        
        return inserted, updated
    
    def _prepare_property_dict(self, prop: PropertyCreate) -> Dict[str, Any]:
        """
        Подготавливает словарь свойства для вставки.
        
        Args:
            prop: PropertyCreate модель
            
        Returns:
            Словарь для вставки в БД
        """
        location = prop.location or {}
        prop_dict = prop.model_dump()
        
        return {
            'source': prop_dict['source'],
            'external_id': prop_dict['external_id'],
            'title': prop_dict['title'],
            'description': prop_dict.get('description'),
            'link': prop_dict.get('link'),
            'price': prop_dict['price'],
            'rooms': prop_dict.get('rooms'),
            'area': prop_dict.get('area'),
            'floor': prop_dict.get('floor'),
            'total_floors': prop_dict.get('total_floors'),
            'city': location.get('city'),
            'district': location.get('district'),
            'address': location.get('address'),
            'latitude': location.get('latitude'),
            'longitude': location.get('longitude'),
            'location': location,
            'photos': prop_dict.get('photos', []),
            'first_seen': datetime.utcnow(),
            'last_seen': datetime.utcnow(),
        }
    
    @staticmethod
    def _chunkify(items: List[Any], chunk_size: int) -> List[List[Any]]:
        """
        Разбивает список на чанки.
        
        Args:
            items: Список для разбивки
            chunk_size: Размер чанка
            
        Returns:
            Список чанков
        """
        return [
            items[i:i + chunk_size]
            for i in range(0, len(items), chunk_size)
        ]


async def batch_insert_properties(
    db: AsyncSession,
    properties: List[PropertyCreate],
    chunk_size: int = 1000,
    use_copy: bool = False
) -> int:
    """
    Быстрая массовая вставка свойств.
    
    Args:
        db: Database session
        properties: Список свойств для вставки
        chunk_size: Размер чанка
        use_copy: Использовать COPY команду (быстрее, но требует direct connection)
        
    Returns:
        Количество вставленных записей
    """
    start_time = time.time()
    
    if not properties:
        return 0
    
    if use_copy:
        # COPY требует прямого подключения к asyncpg
        return await _batch_insert_with_copy(db, properties)
    else:
        # Используем стандартный batch insert
        inserter = BatchPropertyInserter(db, chunk_size=chunk_size)
        inserted, _ = await inserter.insert_with_upsert(properties)
        return inserted


async def _batch_insert_with_copy(
    db: AsyncSession,
    properties: List[PropertyCreate]
) -> int:
    """
    Массовая вставка используя COPY команду.
    
    COPY намного быстрее INSERT для больших объёмов данных,
    но требует прямого подключения к asyncpg и не поддерживает
    ON CONFLICT.
    
    Args:
        db: Database session
        properties: Список свойств
        
    Returns:
        Количество вставленных записей
    """
    from app.db.models.session import get_async_connection
    
    async with get_async_connection() as connection:
        # Подготавливаем данные для COPY
        records = []
        for prop in properties:
            location = prop.location or {}
            prop_dict = prop.model_dump()
            
            records.append((
                prop_dict['source'],
                prop_dict['external_id'],
                prop_dict['title'],
                prop_dict.get('description'),
                prop_dict.get('link'),
                prop_dict['price'],
                prop_dict.get('rooms'),
                prop_dict.get('area'),
                prop_dict.get('floor'),
                prop_dict.get('total_floors'),
                location.get('city'),
                location.get('district'),
                location.get('address'),
                location.get('latitude'),
                location.get('longitude'),
                location,
                prop_dict.get('photos', []),
                datetime.utcnow(),
                datetime.utcnow(),
            ))
        
        # Используем COPY для быстрой вставки
        try:
            await connection.copy_records_to_table(
                'properties',
                records=records,
                columns=[
                    'source', 'external_id', 'title', 'description', 'link',
                    'price', 'rooms', 'area', 'floor', 'total_floors',
                    'city', 'district', 'address', 'latitude', 'longitude',
                    'location', 'photos', 'first_seen', 'last_seen'
                ]
            )
            
            logger.info(f"COPY inserted {len(records)} properties")
            return len(records)
        
        except Exception as e:
            logger.error(f"COPY failed, falling back to batch insert: {e}")
            # Fallback к стандартному batch insert
            return await batch_insert_properties(db, properties, use_copy=False)


async def deduplicate_properties(
    db: AsyncSession,
    properties: List[PropertyCreate]
) -> List[PropertyCreate]:
    """
    Удаляет дубликаты из списка свойств перед вставкой.
    
    Использует комбинацию source + external_id для определения дубликатов.
    
    Args:
        db: Database session
        properties: Список свойств с возможными дубликатами
        
    Returns:
        Список уникальных свойств
    """
    seen = set()
    unique_properties = []
    duplicates_count = 0
    
    for prop in properties:
        # Создаём ключ из source и external_id
        key = (prop.source, prop.external_id)
        
        if key not in seen:
            seen.add(key)
            unique_properties.append(prop)
        else:
            duplicates_count += 1
    
    if duplicates_count > 0:
        logger.info(f"Removed {duplicates_count} duplicate properties")
    
    return unique_properties


async def bulk_upsert_with_deduplication(
    db: AsyncSession,
    properties: List[PropertyCreate],
    chunk_size: int = 1000
) -> Dict[str, int]:
    """
    Комбинированная операция: deduplication + batch upsert.
    
    Args:
        db: Database session
        properties: Список свойств (возможно с дубликатами)
        chunk_size: Размер чанка для batch операций
        
    Returns:
        Статистика операции
    """
    start_time = time.time()
    
    # Шаг 1: Удаляем дубликаты в памяти
    unique_properties = await deduplicate_properties(db, properties)
    duplicates_removed = len(properties) - len(unique_properties)
    
    # Шаг 2: Batch upsert в БД
    inserter = BatchPropertyInserter(db, chunk_size=chunk_size)
    inserted, updated = await inserter.insert_with_upsert(unique_properties)
    
    duration = time.time() - start_time
    
    stats = {
        'total_input': len(properties),
        'duplicates_removed': duplicates_removed,
        'unique_properties': len(unique_properties),
        'inserted': inserted,
        'updated': updated,
        'duration_seconds': duration,
    }
    
    logger.info(
        f"Bulk upsert completed: {stats['inserted']} inserted, "
        f"{stats['updated']} updated, {stats['duplicates_removed']} duplicates removed "
        f"in {duration:.2f}s"
    )
    
    return stats


__all__ = [
    "BatchPropertyInserter",
    "batch_insert_properties",
    "deduplicate_properties",
    "bulk_upsert_with_deduplication",
]
