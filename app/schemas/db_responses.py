"""
Типизированные схемы для CRUD операций.

Использование:
    from app.schemas.db_responses import PropertyResponse, PropertiesListResponse
    
    # Возврат ответа из API
    async def get_property_endpoint() -> PropertyResponse:
        ...
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict

from app.models.schemas import Property


# ============================================================================
# Базовые схемы ответов
# ============================================================================

class APIResponse(BaseModel):
    """Базовая схема ответа API."""

    success: bool = Field(default=True, description="Статус выполнения операции")
    message: Optional[str] = Field(None, description="Сообщение результата")

    model_config = ConfigDict(from_attributes=True)


class PaginatedResponse(BaseModel):
    """Базовая схема пагинированного ответа."""

    items: List[Any] = Field(default_factory=list, description="Список результатов")
    total: int = Field(..., ge=0, description="Общее количество записей")
    skip: int = Field(default=0, ge=0, description="Количество пропущенных записей")
    limit: int = Field(default=100, ge=1, le=100, description="Максимальное количество записей")
    page: int = Field(default=1, ge=1, description="Текущая страница")
    pages: int = Field(default=1, ge=1, description="Общее количество страниц")
    has_next: bool = Field(default=False, description="Есть ли следующая страница")
    has_prev: bool = Field(default=False, description="Есть ли предыдущая страница")

    @classmethod
    def create(
        cls,
        items: List[Any],
        total: int,
        skip: int = 0,
        limit: int = 100
    ) -> "PaginatedResponse":
        """Создает пагинированный ответ."""
        page = (skip // limit) + 1
        pages = (total + limit - 1) // limit if total > 0 else 1

        return cls(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
            page=page,
            pages=pages,
            has_next=page < pages,
            has_prev=page > 1,
        )


# ============================================================================
# Схемы для Property CRUD
# ============================================================================

class PropertyResponse(Property):
    """Ответ с данными объекта недвижимости."""

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "source": "avito",
                "external_id": "123456",
                "title": "2-комнатная квартира",
                "price": 50000,
                "rooms": 2,
                "area": 54.5,
                "city": "Москва",
                "district": "Центральный",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
            }
        }


class PropertyCreateResponse(PropertyResponse):
    """Ответ после создания объекта недвижимости."""

    created: bool = Field(default=True, description="Флаг создания")


class PropertyUpdateResponse(PropertyResponse):
    """Ответ после обновления объекта недвижимости."""

    updated: bool = Field(default=True, description="Флаг обновления")
    changed_fields: Optional[List[str]] = Field(
        None, description="Список измененных полей"
    )


class PropertyDeleteResponse(APIResponse):
    """Ответ после удаления объекта недвижимости."""

    deleted_id: Optional[int] = Field(None, description="ID удаленного объекта")
    deleted_count: int = Field(default=0, description="Количество удаленных записей")


class PropertiesListResponse(PaginatedResponse):
    """Ответ со списком объектов недвижимости."""

    items: List[PropertyResponse] = Field(default_factory=list, description="Список объектов")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Схемы для статистики и аналитики
# ============================================================================

class PropertyStatistics(BaseModel):
    """Статистика по недвижимости."""

    total: int = Field(..., ge=0, description="Общее количество")
    avg_price: Optional[float] = Field(None, ge=0, description="Средняя цена")
    min_price: Optional[float] = Field(None, ge=0, description="Минимальная цена")
    max_price: Optional[float] = Field(None, ge=0, description="Максимальная цена")
    avg_area: Optional[float] = Field(None, ge=0, description="Средняя площадь")
    min_area: Optional[float] = Field(None, ge=0, description="Минимальная площадь")
    max_area: Optional[float] = Field(None, ge=0, description="Максимальная площадь")
    avg_rooms: Optional[float] = Field(None, ge=0, description="Среднее количество комнат")
    avg_price_per_sqm: Optional[float] = Field(None, ge=0, description="Средняя цена за кв.м")


class PropertyPriceChange(BaseModel):
    """Изменение цены объекта."""

    property_id: int = Field(..., description="ID объекта")
    old_price: float = Field(..., ge=0, description="Старая цена")
    new_price: float = Field(..., ge=0, description="Новая цена")
    price_change: float = Field(..., description="Изменение цены")
    price_change_percent: float = Field(..., description="Изменение цены в процентах")
    changed_at: datetime = Field(..., description="Дата изменения")


class PropertyPriceHistoryResponse(BaseModel):
    """История изменения цен."""

    property_id: int = Field(..., description="ID объекта")
    history: List[PropertyPriceChange] = Field(default_factory=list, description="История изменений")
    total_changes: int = Field(default=0, description="Общее количество изменений")
    min_price: Optional[float] = Field(None, ge=0, description="Минимальная цена за все время")
    max_price: Optional[float] = Field(None, ge=0, description="Максимальная цена за все время")


# ============================================================================
# Схемы для операций Bulk
# ============================================================================

class BulkOperationResult(BaseModel):
    """Результат массовой операции."""

    success: bool = Field(default=True, description="Статус операции")
    created: int = Field(default=0, ge=0, description="Количество созданных записей")
    updated: int = Field(default=0, ge=0, description="Количество обновленных записей")
    deleted: int = Field(default=0, ge=0, description="Количество удаленных записей")
    errors: int = Field(default=0, ge=0, description="Количество ошибок")
    error_details: Optional[List[Dict[str, Any]]] = Field(
        None, description="Детали ошибок"
    )
    processing_time_ms: Optional[float] = Field(
        None, ge=0, description="Время обработки в мс"
    )


class BulkUpsertResponse(BulkOperationResult):
    """Ответ массовой операции upsert."""

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "created": 10,
                "updated": 5,
                "deleted": 0,
                "errors": 0,
                "processing_time_ms": 150.5,
            }
        }


# ============================================================================
# Схемы для поиска и фильтрации
# ============================================================================

class SearchQueryParams(BaseModel):
    """Параметры поискового запроса."""

    city: Optional[str] = Field(None, min_length=2, max_length=100, description="Город")
    district: Optional[str] = Field(None, min_length=2, max_length=100, description="Район")
    min_price: Optional[int] = Field(None, ge=0, description="Минимальная цена")
    max_price: Optional[int] = Field(None, ge=0, description="Максимальная цена")
    min_rooms: Optional[int] = Field(None, ge=0, description="Минимальное количество комнат")
    max_rooms: Optional[int] = Field(None, ge=0, description="Максимальное количество комнат")
    min_area: Optional[float] = Field(None, ge=0, description="Минимальная площадь")
    max_area: Optional[float] = Field(None, ge=0, description="Максимальная площадь")
    property_type: Optional[str] = Field(None, description="Тип недвижимости")

    model_config = ConfigDict(from_attributes=True)


class SearchQueryResponse(BaseModel):
    """Результат поискового запроса."""

    query_id: int = Field(..., description="ID запроса")
    query_params: SearchQueryParams = Field(..., description="Параметры запроса")
    results_count: int = Field(..., ge=0, description="Количество результатов")
    executed_at: datetime = Field(..., description="Время выполнения")
    execution_time_ms: Optional[float] = Field(None, ge=0, description="Время выполнения в мс")


# ============================================================================
# Схемы для метрик и мониторинга
# ============================================================================

class DBMetrics(BaseModel):
    """Метрики базы данных."""

    total_properties: int = Field(..., ge=0, description="Всего объектов")
    active_properties: int = Field(..., ge=0, description="Активных объектов")
    properties_today: int = Field(..., ge=0, description="Объектов сегодня")
    avg_response_time_ms: Optional[float] = Field(
        None, ge=0, description="Среднее время ответа"
    )
    cache_hit_rate: Optional[float] = Field(
        None, ge=0, le=1, description="Процент попаданий в кеш"
    )


class CRUDOperationMetrics(BaseModel):
    """Метрики CRUD операции."""

    operation: str = Field(..., description="Тип операции")
    count: int = Field(..., ge=0, description="Количество выполнений")
    avg_duration_ms: Optional[float] = Field(
        None, ge=0, description="Средняя длительность в мс"
    )
    min_duration_ms: Optional[float] = Field(
        None, ge=0, description="Минимальная длительность в мс"
    )
    max_duration_ms: Optional[float] = Field(
        None, ge=0, description="Максимальная длительность в мс"
    )
    errors_count: int = Field(default=0, ge=0, description="Количество ошибок")


# ============================================================================
# Схемы ошибок
# ============================================================================

class ErrorResponse(BaseModel):
    """Схема ошибки."""

    error: str = Field(..., description="Код ошибки")
    message: str = Field(..., description="Сообщение ошибки")
    details: Optional[Any] = Field(None, description="Детали ошибки")
    request_id: Optional[str] = Field(None, description="ID запроса")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Время ошибки")

    model_config = ConfigDict(from_attributes=True)


class ValidationErrorDetail(BaseModel):
    """Деталь валидационной ошибки."""

    loc: List[str] = Field(..., description="Путь к полю")
    msg: str = Field(..., description="Сообщение ошибки")
    type: str = Field(..., description="Тип ошибки")


class ValidationErrorResponse(ErrorResponse):
    """Ответ с ошибками валидации."""

    error: str = "validation_error"
    details: List[ValidationErrorDetail] = Field(
        default_factory=list, description="Список ошибок валидации"
    )


# ============================================================================
# Generic типы для репозиториев
# ============================================================================

T = TypeVar("T", bound=BaseModel)


class RepositoryResponse(BaseModel, Generic[T]):
    """Универсальный ответ репозитория."""

    data: Optional[T] = Field(None, description="Данные")
    success: bool = Field(default=True, description="Статус операции")
    message: Optional[str] = Field(None, description="Сообщение")


class RepositoryListResponse(BaseModel, Generic[T]):
    """Универсальный ответ списка репозитория."""

    items: List[T] = Field(default_factory=list, description="Список данных")
    total: int = Field(..., ge=0, description="Общее количество")


__all__ = [
    # Базовые схемы
    "APIResponse",
    "PaginatedResponse",
    # Property схемы
    "PropertyResponse",
    "PropertyCreateResponse",
    "PropertyUpdateResponse",
    "PropertyDeleteResponse",
    "PropertiesListResponse",
    # Статистика
    "PropertyStatistics",
    "PropertyPriceChange",
    "PropertyPriceHistoryResponse",
    # Bulk операции
    "BulkOperationResult",
    "BulkUpsertResponse",
    # Поиск
    "SearchQueryParams",
    "SearchQueryResponse",
    # Метрики
    "DBMetrics",
    "CRUDOperationMetrics",
    # Ошибки
    "ErrorResponse",
    "ValidationErrorDetail",
    "ValidationErrorResponse",
    # Generic
    "RepositoryResponse",
    "RepositoryListResponse",
]
