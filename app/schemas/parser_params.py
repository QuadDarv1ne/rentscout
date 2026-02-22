"""
Схемы валидации параметров для парсеров.

Использование:
    from app.schemas.parser_params import ParserParams, AvitoParserParams
    
    # Валидация параметров
    params = ParserParams(city="Москва", min_price=30000, max_price=100000)
    params.validate()
"""

from datetime import date
from enum import Enum
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# Перечисления
# ============================================================================

class PropertyType(str, Enum):
    """Типы недвижимости."""
    APARTMENT = "Квартира"
    HOUSE = "Дом"
    ROOM = "Комната"
    COMMERCIAL = "Коммерческая"
    LAND = "Участок"
    GARAGE = "Гараж"
    STUDIO = "Студия"


class SortBy(str, Enum):
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


# ============================================================================
# Базовые схемы
# ============================================================================

class BaseParserParams(BaseModel):
    """Базовая схема параметров парсера."""

    class Config:
        extra = "allow"  # Разрешаем дополнительные поля

    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует схему в словарь."""
        return self.model_dump(exclude_none=True)


class LocationParams(BaseParserParams):
    """Параметры местоположения."""

    city: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Город для поиска",
        examples=["Москва", "Санкт-Петербург"]
    )
    district: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Район города",
        examples=["Центральный", "Приморский"]
    )
    address: Optional[str] = Field(
        None,
        max_length=500,
        description="Адрес (улица, дом)",
        examples=["Тверская, 1", "Невский, 100"]
    )
    coordinates: Optional[Dict[str, float]] = Field(
        None,
        description="Координаты (широта, долгота)",
        examples=[{"lat": 55.7558, "lon": 37.6173}]
    )

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: str) -> str:
        """Валидация названия города."""
        if not v.strip():
            raise ValueError("Город не может быть пустым")
        return v.strip().title()

    @field_validator("district")
    @classmethod
    def validate_district(cls, v: Optional[str]) -> Optional[str]:
        """Валидация района."""
        if v and not v.strip():
            raise ValueError("Район не может быть пустой строкой")
        return v.strip().title() if v else v

    @model_validator(mode="after")
    def validate_coordinates(self) -> "LocationParams":
        """Валидация координат."""
        if self.coordinates:
            lat = self.coordinates.get("lat")
            lon = self.coordinates.get("lon")

            if lat is not None and not (-90 <= lat <= 90):
                raise ValueError("Широта должна быть от -90 до 90")
            if lon is not None and not (-180 <= lon <= 180):
                raise ValueError("Долгота должна быть от -180 до 180")

        return self


class PriceParams(BaseParserParams):
    """Параметры цены."""

    min_price: Optional[int] = Field(
        None,
        ge=0,
        le=1_000_000_000,
        description="Минимальная цена",
        examples=[30000]
    )
    max_price: Optional[int] = Field(
        None,
        ge=0,
        le=1_000_000_000,
        description="Максимальная цена",
        examples=[100000]
    )
    currency: Optional[str] = Field(
        "RUB",
        description="Валюта",
        examples=["RUB", "USD", "EUR"]
    )
    max_price_per_sqm: Optional[float] = Field(
        None,
        ge=0,
        description="Максимальная цена за кв.м",
        examples=[200000]
    )

    @model_validator(mode="after")
    def validate_price_range(self) -> "PriceParams":
        """Валидация диапазона цен."""
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError(
                    f"min_price ({self.min_price}) не может быть больше "
                    f"max_price ({self.max_price})"
                )
        return self


class PropertyFeaturesParams(BaseParserParams):
    """Параметры характеристик недвижимости."""

    property_type: Optional[PropertyType] = Field(
        PropertyType.APARTMENT,
        description="Тип недвижимости"
    )
    min_rooms: Optional[int] = Field(
        None,
        ge=0,
        le=10,
        description="Минимальное количество комнат",
        examples=[1]
    )
    max_rooms: Optional[int] = Field(
        None,
        ge=0,
        le=10,
        description="Максимальное количество комнат",
        examples=[3]
    )
    min_area: Optional[float] = Field(
        None,
        ge=0,
        le=10000,
        description="Минимальная площадь (кв.м)",
        examples=[30]
    )
    max_area: Optional[float] = Field(
        None,
        ge=0,
        le=10000,
        description="Максимальная площадь (кв.м)",
        examples=[100]
    )
    min_floor: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Минимальный этаж",
        examples=[3]
    )
    max_floor: Optional[int] = Field(
        None,
        ge=0,
        le=100,
        description="Максимальный этаж",
        examples=[10]
    )
    min_total_floors: Optional[int] = Field(
        None,
        ge=1,
        le=200,
        description="Минимальное количество этажей в доме",
    )
    max_total_floors: Optional[int] = Field(
        None,
        ge=1,
        le=200,
        description="Максимальное количество этажей в доме",
    )

    @model_validator(mode="after")
    def validate_rooms_range(self) -> "PropertyFeaturesParams":
        """Валидация диапазона комнат."""
        if self.min_rooms is not None and self.max_rooms is not None:
            if self.min_rooms > self.max_rooms:
                raise ValueError(
                    f"min_rooms ({self.min_rooms}) не может быть больше "
                    f"max_rooms ({self.max_rooms})"
                )
        return self

    @model_validator(mode="after")
    def validate_area_range(self) -> "PropertyFeaturesParams":
        """Валидация диапазона площади."""
        if self.min_area is not None and self.max_area is not None:
            if self.min_area > self.max_area:
                raise ValueError(
                    f"min_area ({self.min_area}) не может быть больше "
                    f"max_area ({self.max_area})"
                )
        return self

    @model_validator(mode="after")
    def validate_floor_range(self) -> "PropertyFeaturesParams":
        """Валидация диапазона этажей."""
        if self.min_floor is not None and self.max_floor is not None:
            if self.min_floor > self.max_floor:
                raise ValueError(
                    f"min_floor ({self.min_floor}) не может быть больше "
                    f"max_floor ({self.max_floor})"
                )
        return self


class FilterParams(BaseParserParams):
    """Параметры фильтрации."""

    has_photos: Optional[bool] = Field(
        None,
        description="Только с фотографиями"
    )
    is_verified: Optional[bool] = Field(
        None,
        description="Только проверенные объявления"
    )
    source: Optional[str] = Field(
        None,
        description="Источник (avito, cian, и т.д.)",
        examples=["avito", "cian"]
    )
    features: Optional[List[str]] = Field(
        None,
        description="Список требуемых удобств",
        examples=[["балкон", "кондиционер", "парковка"]]
    )
    has_contact: Optional[bool] = Field(
        None,
        description="Только с контактной информацией"
    )


class DateRangeParams(BaseParserParams):
    """Параметры диапазона дат."""

    min_first_seen: Optional[date] = Field(
        None,
        description="Минимальная дата первого появления",
    )
    max_first_seen: Optional[date] = Field(
        None,
        description="Максимальная дата первого появления",
    )
    min_last_seen: Optional[date] = Field(
        None,
        description="Минимальная дата последнего появления",
    )
    max_last_seen: Optional[date] = Field(
        None,
        description="Максимальная дата последнего появления",
    )


class PaginationParams(BaseParserParams):
    """Параметры пагинации."""

    skip: Optional[int] = Field(
        0,
        ge=0,
        le=10000,
        description="Количество пропускаемых записей"
    )
    limit: Optional[int] = Field(
        100,
        ge=1,
        le=100,
        description="Максимальное количество записей в ответе"
    )


class SortParams(BaseParserParams):
    """Параметры сортировки."""

    sort_by: Optional[SortBy] = Field(
        None,
        description="Поле для сортировки"
    )
    sort_order: Optional[SortOrder] = Field(
        SortOrder.DESC,
        description="Порядок сортировки"
    )


# ============================================================================
# Основная схема параметров парсера
# ============================================================================

class ParserParams(
    LocationParams,
    PriceParams,
    PropertyFeaturesParams,
    FilterParams,
    DateRangeParams,
    PaginationParams,
    SortParams
):
    """
    Основная схема параметров для парсеров недвижимости.

    Объединяет все параметры валидации в одной схеме.

    Пример использования:
        params = ParserParams(
            city="Москва",
            min_price=30000,
            max_price=100000,
            min_rooms=1,
            max_rooms=3,
            has_photos=True
        )
        params_dict = params.to_dict()
    """

    class Config:
        extra = "allow"
        json_schema_extra = {
            "example": {
                "city": "Москва",
                "district": "Центральный",
                "min_price": 30000,
                "max_price": 100000,
                "min_rooms": 1,
                "max_rooms": 3,
                "min_area": 30,
                "max_area": 100,
                "property_type": "Квартира",
                "has_photos": True,
                "sort_by": "price",
                "sort_order": "asc",
                "limit": 50,
            }
        }


# ============================================================================
# Специфичные схемы для отдельных парсеров
# ============================================================================

class AvitoParserParams(ParserParams):
    """Параметры для парсера Avito."""

    avito_specific_field: Optional[str] = Field(
        None,
        description="Специфичное поле Avito"
    )


class CianParserParams(ParserParams):
    """Параметры для парсера Cian."""

    cian_specific_field: Optional[str] = Field(
        None,
        description="Специфичное поле Cian"
    )


class DomofondParserParams(ParserParams):
    """Параметры для парсера Domofond."""

    domofond_specific_field: Optional[str] = Field(
        None,
        description="Специфичное поле Domofond"
    )


class YandexRealtyParserParams(ParserParams):
    """Параметры для парсера Yandex Realty."""

    yandex_specific_field: Optional[str] = Field(
        None,
        description="Специфичное поле Yandex"
    )


class DomclickParserParams(ParserParams):
    """Параметры для парсера Domclick."""

    domclick_specific_field: Optional[str] = Field(
        None,
        description="Специфичное поле Domclick"
    )


# ============================================================================
# Утилиты
# ============================================================================

def create_parser_params(
    source: str,
    **kwargs
) -> ParserParams:
    """
    Фабричная функция для создания параметров парсера.

    Args:
        source: Источник (avito, cian, и т.д.)
        **kwargs: Параметры для валидации

    Returns:
        Валидированный объект параметров

    Raises:
        ValidationError: При невалидных параметрах
    """
    source_to_params = {
        "avito": AvitoParserParams,
        "cian": CianParserParams,
        "domofond": DomofondParserParams,
        "yandex_realty": YandexRealtyParserParams,
        "domclick": DomclickParserParams,
    }

    params_class = source_to_params.get(source.lower(), ParserParams)
    return params_class(**kwargs)


__all__ = [
    # Перечисления
    "PropertyType",
    "SortBy",
    "SortOrder",
    # Базовые схемы
    "BaseParserParams",
    "LocationParams",
    "PriceParams",
    "PropertyFeaturesParams",
    "FilterParams",
    "DateRangeParams",
    "PaginationParams",
    "SortParams",
    # Основная схема
    "ParserParams",
    # Специфичные схемы
    "AvitoParserParams",
    "CianParserParams",
    "DomofondParserParams",
    "YandexRealtyParserParams",
    "DomclickParserParams",
    # Утилиты
    "create_parser_params",
]
