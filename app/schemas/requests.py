"""
Схемы запросов API на Pydantic v2.

Централизованная валидация всех входных данных API.
"""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class PropertyType(str, Enum):
    """Типы недвижимости."""
    APARTMENT = "Квартира"
    HOUSE = "Дом"
    ROOM = "Комната"
    COMMERCIAL = "Коммерческая"
    LAND = "Участок"


class SortField(str, Enum):
    """Поля для сортировки."""
    PRICE = "price"
    AREA = "area"
    ROOMS = "rooms"
    FLOOR = "floor"
    FIRST_SEEN = "first_seen"
    LAST_SEEN = "last_seen"


class SortOrder(str, Enum):
    """Порядок сортировки."""
    ASC = "asc"
    DESC = "desc"


class SourceEnum(str, Enum):
    """Источники данных."""
    AVITO = "avito"
    CIAN = "cian"
    DOMOFOND = "domofond"
    YANDEX_REALTY = "yandex_realty"
    DOMCLICK = "domclick"
    SUTOCHNO = "sutochno"
    OSTROVOK = "ostrovok"


# ============================================================================
# Search Request Schemas
# ============================================================================

class PropertySearchRequest(BaseModel):
    """
    Базовый запрос поиска недвижимости.

    Пример:
        {
            "city": "Москва",
            "min_price": 30000,
            "max_price": 100000,
            "min_rooms": 1,
            "max_rooms": 3
        }
    """
    model_config = ConfigDict(str_strip_whitespace=True)

    city: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Город для поиска",
        examples=["Москва", "Санкт-Петербург"]
    )
    property_type: Optional[PropertyType] = Field(
        default=PropertyType.APARTMENT,
        description="Тип недвижимости"
    )

    # Ценовые фильтры
    min_price: Optional[int] = Field(
        default=None,
        ge=0,
        le=1_000_000_000,
        description="Минимальная цена",
        examples=[30000]
    )
    max_price: Optional[int] = Field(
        default=None,
        ge=0,
        le=1_000_000_000,
        description="Максимальная цена",
        examples=[100000]
    )

    # Фильтры по комнатам
    min_rooms: Optional[int] = Field(
        default=None,
        ge=0,
        le=10,
        description="Минимальное количество комнат",
        examples=[1]
    )
    max_rooms: Optional[int] = Field(
        default=None,
        ge=0,
        le=10,
        description="Максимальное количество комнат",
        examples=[3]
    )

    # Фильтры по площади
    min_area: Optional[float] = Field(
        default=None,
        ge=0,
        le=10000,
        description="Минимальная площадь (кв.м)",
        examples=[30]
    )
    max_area: Optional[float] = Field(
        default=None,
        ge=0,
        le=10000,
        description="Максимальная площадь (кв.м)",
        examples=[100]
    )

    # Фильтры по этажам
    min_floor: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Минимальный этаж",
        examples=[3]
    )
    max_floor: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Максимальный этаж",
        examples=[10]
    )
    min_total_floors: Optional[int] = Field(
        default=None,
        ge=1,
        le=200,
        description="Минимальное количество этажей в доме",
    )
    max_total_floors: Optional[int] = Field(
        default=None,
        ge=1,
        le=200,
        description="Максимальное количество этажей в доме",
    )

    # Дополнительные фильтры
    district: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Район города",
        examples=["Центральный", "Приморский"]
    )
    has_photos: Optional[bool] = Field(
        default=None,
        description="Только с фотографиями"
    )
    source: Optional[SourceEnum] = Field(
        default=None,
        description="Фильтр по источнику"
    )
    features: Optional[List[str]] = Field(
        default=None,
        description="Список требуемых удобств",
        examples=[["балкон", "кондиционер"]]
    )
    max_price_per_sqm: Optional[float] = Field(
        default=None,
        ge=0,
        description="Максимальная цена за кв.м",
    )
    has_contact: Optional[bool] = Field(
        default=None,
        description="Только с контактной информацией"
    )

    # Фильтры по датам
    min_first_seen: Optional[datetime] = Field(
        default=None,
        description="Минимальная дата первого появления"
    )
    max_first_seen: Optional[datetime] = Field(
        default=None,
        description="Максимальная дата первого появления"
    )
    min_last_seen: Optional[datetime] = Field(
        default=None,
        description="Минимальная дата последнего появления"
    )
    max_last_seen: Optional[datetime] = Field(
        default=None,
        description="Максимальная дата последнего появления"
    )

    # Сортировка и пагинация
    sort_by: Optional[SortField] = Field(
        default=None,
        description="Поле для сортировки"
    )
    sort_order: Optional[SortOrder] = Field(
        default=SortOrder.DESC,
        description="Порядок сортировки"
    )
    skip: Optional[int] = Field(
        default=0,
        ge=0,
        le=10000,
        description="Количество записей для пропуска"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Максимальное количество записей в ответе"
    )

    @model_validator(mode='after')
    def validate_price_range(self) -> 'PropertySearchRequest':
        """Проверка диапазона цен."""
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError(
                f"min_price ({self.min_price}) не может быть больше max_price ({self.max_price})"
            )
        return self

    @model_validator(mode='after')
    def validate_rooms_range(self) -> 'PropertySearchRequest':
        """Проверка диапазона комнат."""
        if (
            self.min_rooms is not None
            and self.max_rooms is not None
            and self.min_rooms > self.max_rooms
        ):
            raise ValueError(
                f"min_rooms ({self.min_rooms}) не может быть больше max_rooms ({self.max_rooms})"
            )
        return self

    @model_validator(mode='after')
    def validate_area_range(self) -> 'PropertySearchRequest':
        """Проверка диапазона площади."""
        if (
            self.min_area is not None
            and self.max_area is not None
            and self.min_area > self.max_area
        ):
            raise ValueError(
                f"min_area ({self.min_area}) не может быть больше max_area ({self.max_area})"
            )
        return self

    @model_validator(mode='after')
    def validate_floor_range(self) -> 'PropertySearchRequest':
        """Проверка диапазона этажей."""
        if (
            self.min_floor is not None
            and self.max_floor is not None
            and self.min_floor > self.max_floor
        ):
            raise ValueError(
                f"min_floor ({self.min_floor}) не может быть больше max_floor ({self.max_floor})"
            )
        return self


class AdvancedSearchRequest(PropertySearchRequest):
    """
    Расширенный запрос поиска с дополнительными опциями.
    """
    # Геолокация
    latitude: Optional[float] = Field(
        default=None,
        ge=-90,
        le=90,
        description="Широта центра поиска",
    )
    longitude: Optional[float] = Field(
        default=None,
        ge=-180,
        le=180,
        description="Долгота центра поиска",
    )
    radius_km: Optional[float] = Field(
        default=None,
        ge=0.1,
        le=100,
        description="Радиус поиска в км",
    )

    # Ранжирование
    enable_ranking: bool = Field(
        default=True,
        description="Включить умное ранжирование результатов"
    )
    ranking_weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Веса для ранжирования (price, area, photos, etc.)"
    )

    # Кэширование
    use_cache: bool = Field(
        default=True,
        description="Использовать кэш"
    )
    force_refresh: bool = Field(
        default=False,
        description="Принудительно обновить кэш"
    )


# ============================================================================
# Property Creation/Update Schemas
# ============================================================================

class PropertyCreateRequest(BaseModel):
    """Запрос на создание недвижимости."""
    model_config = ConfigDict(str_strip_whitespace=True)

    source: str = Field(..., min_length=1, max_length=50)
    external_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=10000)
    link: Optional[str] = Field(default=None, max_length=2000)

    price: float = Field(..., ge=0, le=1_000_000_000)
    currency: Optional[str] = Field(default="RUB", max_length=3)
    price_per_sqm: Optional[float] = Field(default=None, ge=0)

    rooms: Optional[int] = Field(default=None, ge=0, le=20)
    area: Optional[float] = Field(default=None, ge=0, le=10000)
    floor: Optional[int] = Field(default=None, ge=0, le=200)
    total_floors: Optional[int] = Field(default=None, ge=0, le=500)

    city: Optional[str] = Field(default=None, max_length=100)
    district: Optional[str] = Field(default=None, max_length=200)
    address: Optional[str] = Field(default=None, max_length=500)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    photos: List[str] = Field(default_factory=list)
    features: Optional[Dict[str, Any]] = Field(default=None)
    contact_name: Optional[str] = Field(default=None, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=50)

    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)


class PropertyUpdateRequest(BaseModel):
    """Запрос на обновление недвижимости."""
    model_config = ConfigDict(str_strip_whitespace=True)

    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=10000)
    link: Optional[str] = Field(default=None, max_length=2000)

    price: Optional[float] = Field(default=None, ge=0, le=1_000_000_000)
    currency: Optional[str] = Field(default=None, max_length=3)

    rooms: Optional[int] = Field(default=None, ge=0, le=20)
    area: Optional[float] = Field(default=None, ge=0, le=10000)
    floor: Optional[int] = Field(default=None, ge=0, le=200)
    total_floors: Optional[int] = Field(default=None, ge=0, le=500)

    district: Optional[str] = Field(default=None, max_length=200)
    address: Optional[str] = Field(default=None, max_length=500)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)

    photos: Optional[List[str]] = Field(default=None)
    features: Optional[Dict[str, Any]] = Field(default=None)
    contact_name: Optional[str] = Field(default=None, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=50)

    is_active: Optional[bool] = Field(default=None)
    is_verified: Optional[bool] = Field(default=None)


# ============================================================================
# Auth Schemas
# ============================================================================

class UserRegisterRequest(BaseModel):
    """Запрос регистрации пользователя."""
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Email адрес",
        examples=["user@example.com"]
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Пароль (минимум 8 символов)",
        examples=["SecureP@ssw0rd!"]
    )
    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=50,
        description="Имя пользователя",
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Валидация email."""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Некорректный email адрес')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Валидация сложности пароля."""
        if len(v) < 8:
            raise ValueError('Пароль должен содержать минимум 8 символов')
        if not any(c.isupper() for c in v):
            raise ValueError('Пароль должен содержать заглавную букву')
        if not any(c.isdigit() for c in v):
            raise ValueError('Пароль должен содержать цифру')
        return v


class UserLoginRequest(BaseModel):
    """Запрос входа пользователя."""
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(..., description="Email")
    password: str = Field(..., description="Пароль")


class TokenRefreshRequest(BaseModel):
    """Запрос обновления токена."""
    refresh_token: str = Field(..., description="Refresh токен")


# ============================================================================
# Notification Schemas
# ============================================================================

class CreateNotificationRequest(BaseModel):
    """Запрос создания уведомления."""

    notification_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Тип уведомления",
        examples=["new_property", "price_drop", "alert_triggered"]
    )
    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=2000)
    data: Optional[Dict[str, Any]] = Field(default=None)


class UserNotificationPreferences(BaseModel):
    """Настройки уведомлений пользователя."""

    email_enabled: bool = Field(default=True)
    telegram_enabled: bool = Field(default=False)
    push_enabled: bool = Field(default=True)

    notify_new_properties: bool = Field(default=True)
    notify_price_drops: bool = Field(default=True)
    notify_alerts: bool = Field(default=True)


# ============================================================================
# Bookmark Schemas
# ============================================================================

class CreateBookmarkRequest(BaseModel):
    """Запрос создания закладки."""
    property_id: int = Field(..., gt=0, description="ID недвижимости")
    comment: Optional[str] = Field(default=None, max_length=500)
    tags: Optional[List[str]] = Field(default=None)


# ============================================================================
# ML Prediction Schemas
# ============================================================================

class PricePredictionRequest(BaseModel):
    """Запрос предсказания цены."""

    city: str = Field(..., min_length=1, max_length=100)
    rooms: int = Field(..., ge=0, le=10)
    area: float = Field(..., gt=0, le=10000)
    floor: Optional[int] = Field(default=None, ge=0, le=200)
    total_floors: Optional[int] = Field(default=None, ge=1, le=500)
    district: Optional[str] = Field(default=None, max_length=200)


class TrendAnalysisRequest(BaseModel):
    """Запрос анализа трендов."""

    city: str = Field(..., min_length=1, max_length=100)
    property_type: Optional[PropertyType] = Field(default=PropertyType.APARTMENT)
    days: int = Field(default=30, ge=1, le=365)


# ============================================================================
# Export Schemas
# ============================================================================

class ExportFormat(str, Enum):
    """Форматы экспорта."""
    JSON = "json"
    CSV = "csv"
    JSONL = "jsonl"
    XLSX = "xlsx"


class ExportRequest(BaseModel):
    """Запрос экспорта данных."""

    format: ExportFormat = Field(default=ExportFormat.JSON)
    search_criteria: Optional[PropertySearchRequest] = Field(default=None)
    property_ids: Optional[List[int]] = Field(default=None)
    include_fields: Optional[List[str]] = Field(default=None)


# ============================================================================
# Response Schemas (базовые)
# ============================================================================

class APIResponse(BaseModel):
    """Базовый ответ API."""
    success: bool = Field(default=True)
    message: Optional[str] = Field(default=None)


class PaginatedResponse(BaseModel):
    """Пагинированный ответ."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: List[Any]
    total: int
    skip: int
    limit: int
    has_more: bool = False

    @property
    def page(self) -> int:
        return (self.skip // self.limit) + 1 if self.limit > 0 else 1


# ============================================================================
# Экспорт
# ============================================================================

__all__ = [
    # Enums
    "PropertyType",
    "SortField",
    "SortOrder",
    "SourceEnum",
    "ExportFormat",

    # Search
    "PropertySearchRequest",
    "AdvancedSearchRequest",

    # Property
    "PropertyCreateRequest",
    "PropertyUpdateRequest",

    # Auth
    "UserRegisterRequest",
    "UserLoginRequest",
    "TokenRefreshRequest",

    # Notifications
    "CreateNotificationRequest",
    "UserNotificationPreferences",

    # Bookmarks
    "CreateBookmarkRequest",

    # ML
    "PricePredictionRequest",
    "TrendAnalysisRequest",

    # Export
    "ExportRequest",

    # Responses
    "APIResponse",
    "PaginatedResponse",
]
