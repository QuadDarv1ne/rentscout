"""
Утилиты для безопасной работы с SQL.

Предотвращение SQL injection и оптимизация запросов.

Использование:
    from app.db.safe_sql import safe_execute, SafeQuery
    
    # Безопасный запрос с параметрами
    result = await safe_execute(
        db,
        "SELECT * FROM properties WHERE city = :city AND price <= :max_price",
        {"city": "Москва", "max_price": 100000}
    )
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime

from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.utils.metrics import metrics_collector
from app.utils.logger import logger

# ============================================================================
# Безопасное выполнение SQL запросов
# ============================================================================


class SQLInjectionError(ValueError):
    """Исключение при попытке SQL injection."""
    pass


class SafeSQLConfig:
    """Конфигурация безопасности SQL."""

    # Запрещенные паттерны (потенциальный SQL injection)
    DANGEROUS_PATTERNS = [
        r";\s*DROP\s+",
        r";\s*DELETE\s+",
        r";\s*UPDATE\s+.*\s+SET\s+",
        r";\s*INSERT\s+",
        r";\s*CREATE\s+",
        r";\s*ALTER\s+",
        r";\s*TRUNCATE\s+",
        r"--",  # SQL комментарий
        r"/\*.*\*/",  # Многострочный комментарий
        r"\bEXEC\s*\(",
        r"\bEXECUTE\s+",
        r"\bsp_\w+",  # Храненые процедуры
        r"\bxp_\w+",  # Расширенные хранимые процедуры
        r"\bWAITFOR\s+DELAY",  # Time-based injection
        r"\bBENCHMARK\s*\(",
        r"\bSLEEP\s*\(",
        r"\bUNION\s+.*\bSELECT\b",  # UNION injection (только с SELECT)
        r"\bOR\s+1\s*=\s*1",  # Classic injection
        r"\bOR\s+'1'\s*=\s*'1'",
        r"\bAND\s+1\s*=\s*1",
    ]

    # Разрешенные типы запросов
    ALLOWED_QUERY_TYPES = ["SELECT", "INSERT", "UPDATE", "DELETE", "WITH"]

    @classmethod
    def is_safe_query(cls, query: str) -> Tuple[bool, Optional[str]]:
        """
        Проверяет безопасность SQL запроса.

        Args:
            query: SQL запрос для проверки

        Returns:
            Кортеж (безопасен, причина если небезопасен)
        """
        query_upper = query.upper()

        # Проверка на запрещенные паттерны
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, query_upper, re.IGNORECASE):
                return False, f"Обнаружен опасный паттерн: {pattern}"

        # Проверка типа запроса
        query_type = query_upper.strip().split()[0] if query_upper.strip() else ""
        if query_type not in cls.ALLOWED_QUERY_TYPES:
            return False, f"Недопустимый тип запроса: {query_type}"

        return True, None


def sanitize_identifier(identifier: str) -> str:
    """
    Очищает SQL идентификатор (имя таблицы, колонки).

    Args:
        identifier: Идентификатор для очистки

    Returns:
        Безопасный идентификатор

    Raises:
        SQLInjectionError: Если идентификатор содержит опасные символы
    """
    if not identifier:
        raise SQLInjectionError("Идентификатор не может быть пустым")

    # Разрешаем * для SELECT *
    if identifier == "*":
        return "*"

    # Разрешаем только буквы, цифры и подчеркивание
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
        raise SQLInjectionError(
            f"Идентификатор '{identifier}' содержит недопустимые символы"
        )

    return identifier


def sanitize_column_name(column: str) -> str:
    """
    Очищает имя колонки для ORDER BY и других конструкций.

    Args:
        column: Имя колонки

    Returns:
        Безопасное имя колонки
    """
    return sanitize_identifier(column)


def sanitize_sort_order(order: str) -> str:
    """
    Очищает направление сортировки.

    Args:
        order: Направление сортировки (ASC/DESC)

    Returns:
        'ASC' или 'DESC'
    """
    order_upper = order.upper().strip()
    if order_upper not in ('ASC', 'DESC'):
        return 'ASC'
    return order_upper


async def safe_execute(
    db: AsyncSession,
    query: str,
    params: Optional[Dict[str, Any]] = None,
    check_safety: bool = True
) -> Any:
    """
    Безопасное выполнение SQL запроса.

    Args:
        db: Сессия базы данных
        query: SQL запрос
        params: Параметры запроса (обязательно использовать именованные параметры)
        check_safety: Проверять ли запрос на безопасность

    Returns:
        Результат выполнения запроса

    Raises:
        SQLInjectionError: Если запрос небезопасен
        ValueError: Если используются позиционные параметры вместо именованных
    """
    # Проверка безопасности
    if check_safety:
        is_safe, reason = SafeSQLConfig.is_safe_query(query)
        if not is_safe:
            logger.warning(f"SQL injection attempt detected: {reason}")
            raise SQLInjectionError(reason)

    # Проверка на позиционные параметры (%s, ?)
    if '%s' in query or (query.count('?') > 0 and ':' not in query):
        logger.warning("Positional parameters detected in SQL query")
        raise ValueError(
            "Используйте именованные параметры (:param) вместо позиционных (%s, ?)"
        )

    # Проверка параметров на опасные значения
    if params:
        for key, value in params.items():
            if isinstance(value, str):
                # Проверяем только явные SQL injection паттерны в значениях
                # Не проверяем тип запроса, только опасные конструкции
                for pattern in SafeSQLConfig.DANGEROUS_PATTERNS:
                    if re.search(pattern, value, re.IGNORECASE):
                        logger.warning(f"SQL injection in parameter '{key}': {pattern}")
                        raise SQLInjectionError(f"Опасное значение параметра '{key}': обнаружен паттерн {pattern}")

    # Выполнение запроса
    start_time = datetime.utcnow()
    try:
        result = await db.execute(text(query), params or {})
        duration = (datetime.utcnow() - start_time).total_seconds()

        # Логирование медленных запросов
        if duration > 1.0:
            logger.warning(f"Slow query ({duration:.2f}s): {query[:100]}...")

        # Метрики
        query_type = query.strip().upper().split()[0] if query.strip() else "UNKNOWN"
        metrics_collector.record_db_query(query_type, "raw_sql", duration)

        return result

    except Exception as e:
        duration = (datetime.utcnow() - start_time).total_seconds()
        metrics_collector.record_db_error("raw_sql", str(e), duration)
        raise


def safe_order_by(
    query: select,
    order_column: str,
    order_direction: str = "ASC",
    allowed_columns: Optional[List[str]] = None
) -> select:
    """
    Безопасная сортировка запроса.

    Args:
        query: SQLAlchemy select запрос
        order_column: Имя колонки для сортировки
        order_direction: Направление сортировки (ASC/DESC)
        allowed_columns: Список разрешенных колонок

    Returns:
        Запрос с сортировкой

    Raises:
        SQLInjectionError: Если колонка не разрешена
    """
    # Очистка имени колонки
    clean_column = sanitize_column_name(order_column)

    # Проверка whitelist если указан
    if allowed_columns and clean_column not in allowed_columns:
        raise SQLInjectionError(
            f"Сортировка по колонке '{clean_column}' не разрешена. "
            f"Разрешенные: {', '.join(allowed_columns)}"
        )

    # Очистка направления
    clean_direction = sanitize_sort_order(order_direction)

    # Применение сортировки
    if clean_direction == "DESC":
        return query.order_by(desc(text(clean_column)))
    else:
        return query.order_by(text(clean_column))


# ============================================================================
# Оптимизация N+1 запросов
# ============================================================================

class N1POptimizer:
    """Утилиты для оптимизации N+1 запросов."""

    @staticmethod
    def apply_selectinload(
        query: select,
        model: Any,
        *relationships: str
    ) -> select:
        """
        Применяет selectinload для отношений.

        Args:
            query: SQLAlchemy select запрос
            model: Модель SQLAlchemy
            relationships: Имена отношений для eager loading

        Returns:
            Запрос с примененным selectinload

        Example:
            query = select(Property)
            query = N1POptimizer.apply_selectinload(query, Property, 'photos', 'owner')
        """
        for rel in relationships:
            try:
                attr = getattr(model, rel)
                query = query.options(selectinload(attr))
            except AttributeError:
                logger.warning(f"Relationship '{rel}' not found on {model.__name__}")

        return query

    @staticmethod
    def apply_joinedload(
        query: select,
        model: Any,
        *relationships: str
    ) -> select:
        """
        Применяет joinedload для отношений.

        Args:
            query: SQLAlchemy select запрос
            model: Модель SQLAlchemy
            relationships: Имена отношений для eager loading

        Returns:
            Запрос с примененным joinedload
        """
        for rel in relationships:
            try:
                attr = getattr(model, rel)
                query = query.options(joinedload(attr))
            except AttributeError:
                logger.warning(f"Relationship '{rel}' not found on {model.__name__}")

        return query

    @staticmethod
    def batch_load(
        items: List[Any],
        relationship: str,
        loader_func: callable,
        key_attr: str = "id"
    ) -> Dict[int, List[Any]]:
        """
        Загружает отношения батчем для списка объектов.

        Args:
            items: Список объектов
            relationship: Имя отношения
            loader_func: Функция для загрузки (принимает список ID)
            key_attr: Атрибут ключа

        Returns:
            Словарь {id: [related_items]}

        Example:
            properties = await get_properties()
            photos = N1POptimizer.batch_load(
                properties,
                'photos',
                get_photos_by_property_ids,
                'id'
            )
        """
        if not items:
            return {}

        # Получаем ID всех объектов
        ids = [getattr(item, key_attr) for item in items]

        # Загружаем все отношения одним запросом
        related_items = loader_func(ids)

        # Группируем по ID (предполагаем что у related_items есть атрибут {key_attr}_id)
        result = {}
        foreign_key_attr = f"{relationship[:-1]}_id" if relationship.endswith('s') else f"{relationship}_id"

        for item in related_items:
            if hasattr(item, foreign_key_attr):
                foreign_key = getattr(item, foreign_key_attr)
            else:
                # Пытаемся найти атрибут с id
                for attr in dir(item):
                    if attr.endswith('_id') and attr != key_attr:
                        foreign_key = getattr(item, attr)
                        break
                else:
                    continue

            if foreign_key not in result:
                result[foreign_key] = []
            result[foreign_key].append(item)

        return result


# ============================================================================
# Безопасные паттерны запросов
# ============================================================================

class SafeQuery:
    """
    Конструктор безопасных SQL запросов.

    Example:
        query = (SafeQuery()
            .select("id", "name", "price")
            .from_table("properties")
            .where("city = :city", {"city": "Москва"})
            .order_by("price", "DESC")
            .limit(100)
            .build())

        result = await safe_execute(db, query["sql"], query["params"])
    """

    def __init__(self):
        self._select_columns: List[str] = []
        self._from_table: Optional[str] = None
        self._where_clauses: List[str] = []
        self._where_params: Dict[str, Any] = {}
        self._order_by: Optional[str] = None
        self._order_direction: str = "ASC"
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._param_counter: int = 0

    def select(self, *columns: str) -> "SafeQuery":
        """Добавляет колонки для выбора."""
        for col in columns:
            self._select_columns.append(sanitize_identifier(col))
        return self

    def from_table(self, table: str) -> "SafeQuery":
        """Указывает таблицу."""
        self._from_table = sanitize_identifier(table)
        return self

    def where(self, condition: str, params: Optional[Dict[str, Any]] = None) -> "SafeQuery":
        """
        Добавляет WHERE условие.

        Args:
            condition: SQL условие с именованными параметрами
            params: Параметры условия
        """
        self._where_clauses.append(condition)
        if params:
            self._where_params.update(params)
        return self

    def order_by(self, column: str, direction: str = "ASC") -> "SafeQuery":
        """Добавляет сортировку."""
        self._order_by = sanitize_column_name(column)
        self._order_direction = sanitize_sort_order(direction)
        return self

    def limit(self, limit: int) -> "SafeQuery":
        """Устанавливает лимит."""
        if limit < 0 or limit > 10000:
            raise ValueError("LIMIT должен быть от 0 до 10000")
        self._limit = limit
        return self

    def offset(self, offset: int) -> "SafeQuery":
        """Устанавливает смещение."""
        if offset < 0:
            raise ValueError("OFFSET не может быть отрицательным")
        self._offset = offset
        return self

    def build(self) -> Dict[str, Any]:
        """
        Строит финальный SQL запрос.

        Returns:
            Словарь {'sql': str, 'params': dict}
        """
        if not self._from_table:
            raise ValueError("Необходимо указать таблицу через from_table()")

        # SELECT часть
        columns = ", ".join(self._select_columns) if self._select_columns else "*"
        sql = f"SELECT {columns} FROM {self._from_table}"

        # WHERE часть
        if self._where_clauses:
            sql += " WHERE " + " AND ".join(self._where_clauses)

        # ORDER BY
        if self._order_by:
            sql += f" ORDER BY {self._order_by} {self._order_direction}"

        # LIMIT и OFFSET
        if self._limit is not None:
            sql += f" LIMIT {self._limit}"
        if self._offset is not None:
            sql += f" OFFSET {self._offset}"

        return {
            "sql": sql,
            "params": self._where_params,
        }


# ============================================================================
# Экспорты
# ============================================================================

__all__ = [
    # Исключения
    "SQLInjectionError",
    # Функции
    "safe_execute",
    "sanitize_identifier",
    "sanitize_column_name",
    "sanitize_sort_order",
    "safe_order_by",
    # Классы
    "SafeSQLConfig",
    "N1POptimizer",
    "SafeQuery",
]
