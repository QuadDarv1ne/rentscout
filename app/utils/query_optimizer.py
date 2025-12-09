"""
Оптимизация запросов к БД через предварительную загрузку и пакетную обработку.

Включает:
- Eager loading (JOIN вместо N+1 queries)
- Batch loading для оптимизации
- Query result caching
- Index hints для оптимизации
"""
from typing import List, Optional, Dict, Any, Type, TypeVar
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

T = TypeVar('T')


class QueryOptimizer:
    """
    Оптимизатор SQL запросов для асинхронных операций.
    
    Основные техники:
    - Предварительная загрузка связанных объектов
    - Пакетная загрузка вместо N+1
    - Кеширование результатов
    - Использование индексов
    """
    
    def __init__(self, session: AsyncSession):
        """
        Инициализация оптимизатора.
        
        Args:
            session: SQLAlchemy async сессия
        """
        self.session = session
        self._cache: Dict[str, tuple[datetime, List[Any]]] = {}
        self.cache_ttl = 300  # 5 минут по умолчанию
        
    async def get_by_id(
        self,
        model: Type[T],
        id: int,
        eager_load: Optional[List[str]] = None
    ) -> Optional[T]:
        """
        Получение объекта по ID с опциональной предварительной загрузкой.
        
        Args:
            model: SQLAlchemy модель
            id: ID объекта
            eager_load: Список отношений для eagerly loading
            
        Returns:
            Объект модели или None
        """
        try:
            query = select(model).where(model.id == id)
            
            # Добавление eager loading
            if eager_load:
                for relation in eager_load:
                    query = query.options(selectinload(getattr(model, relation)))
                    
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error fetching {model.__name__} by id {id}: {e}")
            return None
            
    async def get_batch(
        self,
        model: Type[T],
        ids: List[int],
        eager_load: Optional[List[str]] = None
    ) -> List[T]:
        """
        Пакетная загрузка объектов по списку ID.
        
        Вместо N отдельных запросов делает 1 запрос.
        
        Args:
            model: SQLAlchemy модель
            ids: Список ID
            eager_load: Список отношений для eagerly loading
            
        Returns:
            Список объектов модели
        """
        if not ids:
            return []
            
        try:
            query = select(model).where(model.id.in_(ids))
            
            # Добавление eager loading
            if eager_load:
                for relation in eager_load:
                    query = query.options(selectinload(getattr(model, relation)))
                    
            result = await self.session.execute(query)
            return result.scalars().unique().all()
            
        except Exception as e:
            logger.error(f"Error batch fetching {model.__name__}: {e}")
            return []
            
    async def get_all(
        self,
        model: Type[T],
        filters: Optional[Dict[str, Any]] = None,
        eager_load: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        use_cache: bool = True
    ) -> List[T]:
        """
        Получение всех объектов с опциональной фильтрацией.
        
        Args:
            model: SQLAlchemy модель
            filters: Словарь фильтров {field_name: value}
            eager_load: Список отношений для eager loading
            limit: Лимит результатов
            offset: Смещение
            use_cache: Использовать ли кеш
            
        Returns:
            Список объектов модели
        """
        # Проверка кеша
        cache_key = f"{model.__name__}:{filters}:{limit}:{offset}"
        if use_cache and cache_key in self._cache:
            timestamp, cached_data = self._cache[cache_key]
            if datetime.now() - timestamp < timedelta(seconds=self.cache_ttl):
                logger.debug(f"Cache hit for {cache_key}")
                return cached_data
                
        try:
            query = select(model)
            
            # Применение фильтров
            if filters:
                conditions = []
                for field_name, value in filters.items():
                    if hasattr(model, field_name):
                        conditions.append(
                            getattr(model, field_name) == value
                        )
                if conditions:
                    query = query.where(and_(*conditions))
                    
            # Добавление eager loading
            if eager_load:
                for relation in eager_load:
                    query = query.options(selectinload(getattr(model, relation)))
                    
            # Пагинация
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
                
            result = await self.session.execute(query)
            data = result.scalars().unique().all()
            
            # Сохранение в кеш
            if use_cache:
                self._cache[cache_key] = (datetime.now(), data)
                
            return data
            
        except Exception as e:
            logger.error(f"Error fetching all {model.__name__}: {e}")
            return []
            
    async def count(
        self,
        model: Type[T],
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Подсчёт объектов с опциональной фильтрацией.
        
        Args:
            model: SQLAlchemy модель
            filters: Словарь фильтров
            
        Returns:
            Количество объектов
        """
        try:
            from sqlalchemy import func
            query = select(func.count(model.id))
            
            # Применение фильтров
            if filters:
                conditions = []
                for field_name, value in filters.items():
                    if hasattr(model, field_name):
                        conditions.append(
                            getattr(model, field_name) == value
                        )
                if conditions:
                    query = query.where(and_(*conditions))
                    
            result = await self.session.execute(query)
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Error counting {model.__name__}: {e}")
            return 0
            
    async def bulk_insert(
        self,
        model: Type[T],
        objects: List[T],
        batch_size: int = 100
    ) -> int:
        """
        Пакетная вставка объектов.
        
        Для больших объёмов данных разбивает на батчи.
        
        Args:
            model: SQLAlchemy модель
            objects: Список объектов
            batch_size: Размер батча
            
        Returns:
            Количество вставленных объектов
        """
        if not objects:
            return 0
            
        try:
            inserted = 0
            
            # Обработка батчами
            for i in range(0, len(objects), batch_size):
                batch = objects[i:i + batch_size]
                
                for obj in batch:
                    self.session.add(obj)
                    inserted += 1
                    
                # Flush промежуточных результатов
                await self.session.flush()
                
            await self.session.commit()
            logger.info(f"Bulk inserted {inserted} {model.__name__} objects")
            return inserted
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error bulk inserting {model.__name__}: {e}")
            return 0
            
    async def bulk_update(
        self,
        model: Type[T],
        updates: List[Dict[str, Any]],
        id_field: str = 'id',
        batch_size: int = 100
    ) -> int:
        """
        Пакетное обновление объектов.
        
        Args:
            model: SQLAlchemy модель
            updates: Список словарей {id_field: value, field: value, ...}
            id_field: Название поля ID
            batch_size: Размер батча
            
        Returns:
            Количество обновлённых объектов
        """
        if not updates:
            return 0
            
        try:
            updated = 0
            
            # Обработка батчами
            for i in range(0, len(updates), batch_size):
                batch = updates[i:i + batch_size]
                
                for update_dict in batch:
                    # Извлечение ID
                    obj_id = update_dict.pop(id_field)
                    
                    # Выполнение обновления
                    query = select(model).where(
                        getattr(model, id_field) == obj_id
                    )
                    result = await self.session.execute(query)
                    obj = result.scalar_one_or_none()
                    
                    if obj:
                        for field, value in update_dict.items():
                            if hasattr(obj, field):
                                setattr(obj, field, value)
                        updated += 1
                        
                # Flush промежуточных результатов
                await self.session.flush()
                
            await self.session.commit()
            logger.info(f"Bulk updated {updated} {model.__name__} objects")
            return updated
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error bulk updating {model.__name__}: {e}")
            return 0
            
    def clear_cache(self):
        """Очистка кеша."""
        self._cache.clear()
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Получение статистики кеша."""
        return {
            'cached_queries': len(self._cache),
            'cache_ttl': self.cache_ttl
        }


# Пример использования
async def example_usage():
    """Демонстрация использования QueryOptimizer."""
    
    # from app.db.models.property import Property
    # 
    # async with AsyncSession(engine) as session:
    #     optimizer = QueryOptimizer(session)
    #     
    #     # Получение одного объекта с предварительной загрузкой
    #     property = await optimizer.get_by_id(
    #         Property,
    #         id=1,
    #         eager_load=['owner', 'reviews']
    #     )
    #     
    #     # Пакетная загрузка
    #     properties = await optimizer.get_batch(
    #         Property,
    #         ids=[1, 2, 3, 4, 5],
    #         eager_load=['owner']
    #     )
    #     
    #     # Получение с фильтрацией и пагинацией
    #     filtered_properties = await optimizer.get_all(
    #         Property,
    #         filters={'city': 'Moscow', 'price_min': 50000},
    #         eager_load=['owner'],
    #         limit=10,
    #         offset=0
    #     )
    #     
    #     # Подсчёт
    #     count = await optimizer.count(
    #         Property,
    #         filters={'city': 'Moscow'}
    #     )
    
    pass
