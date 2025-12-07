from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, ConfigDict, Field


class PropertyBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source: str = Field(..., description="Источник данных (avito, cian и т.д.)", examples=["avito"])
    external_id: str = Field(..., description="Идентификатор объявления на источнике", examples=["123456"])
    title: str = Field(..., description="Заголовок объявления", examples=["2-комнатная квартира"])
    description: Optional[str] = Field(None, description="Описание объявления")
    link: Optional[str] = Field(None, description="Ссылка на объявление", examples=["https://example.com/123"])

    price: float = Field(..., ge=0, description="Цена аренды", examples=[50000])
    currency: Optional[str] = Field("RUB", description="Валюта цены", examples=["RUB"])
    price_per_sqm: Optional[float] = Field(None, ge=0, description="Цена за квадратный метр")

    rooms: Optional[int] = Field(None, ge=0, description="Количество комнат")
    area: Optional[float] = Field(None, ge=0, description="Площадь в кв.м")
    floor: Optional[int] = Field(None, ge=0, description="Этаж")
    total_floors: Optional[int] = Field(None, ge=0, description="Всего этажей в доме")

    city: Optional[str] = Field(None, description="Город", examples=["Москва"])
    district: Optional[str] = Field(None, description="Район города")
    address: Optional[str] = Field(None, description="Полный адрес")
    latitude: Optional[float] = Field(None, description="Географическая широта")
    longitude: Optional[float] = Field(None, description="Географическая долгота")
    location: Optional[Dict[str, Any]] = Field(
        None,
        description="Полные данные о местоположении (произвольный JSON)",
        examples=[{"city": "Москва", "address": "Тверская, 1"}],
    )

    photos: List[str] = Field(default_factory=list, description="Список URL фотографий")
    features: Optional[Dict[str, Any]] = Field(None, description="Дополнительные характеристики")
    contact_name: Optional[str] = Field(None, description="Контактное лицо")
    contact_phone: Optional[str] = Field(None, description="Контактный телефон")

    is_active: Optional[bool] = Field(True, description="Активно ли объявление")
    is_verified: Optional[bool] = Field(False, description="Подтверждено ли объявление")


class PropertyCreate(PropertyBase):
    pass


class Property(PropertyBase):
    id: Optional[int] = Field(None, description="Внутренний идентификатор записи")
    first_seen: Optional[datetime] = Field(None, description="Когда объявление впервые увидели")
    last_seen: Optional[datetime] = Field(None, description="Когда объявление видели в последний раз")
    created_at: Optional[datetime] = Field(None, description="Дата создания записи")
    last_updated: Optional[datetime] = Field(None, description="Дата последнего обновления записи")

    model_config = ConfigDict(from_attributes=True)


class PropertyPriceHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = Field(None, description="Идентификатор записи истории")
    property_id: int = Field(..., description="ID объявления")
    old_price: Optional[float] = Field(None, description="Старая цена")
    new_price: float = Field(..., description="Новая цена")
    price_change: Optional[float] = Field(None, description="Изменение цены")
    price_change_percent: Optional[float] = Field(None, description="Изменение цены в процентах")
    changed_at: Optional[datetime] = Field(None, description="Время изменения")


class PropertyStatistics(BaseModel):
    total: int
    avg_price: Optional[float]
    min_price: Optional[float]
    max_price: Optional[float]
    avg_area: Optional[float]
    min_area: Optional[float]
    max_area: Optional[float]
    avg_rooms: Optional[float]


class PopularProperty(BaseModel):
    property: Property
    view_count: int


class PopularSearch(BaseModel):
    city: Optional[str]
    property_type: Optional[str]
    count: int


class BulkUpsertResult(BaseModel):
    created: int
    updated: int
    errors: int


class OperationStatus(BaseModel):
    status: str = Field(..., examples=["ok"])
    message: Optional[str] = None


class DeactivateResult(BaseModel):
    status: str = Field(..., examples=["ok"])
    deactivated_count: int


class PaginatedProperties(BaseModel):
    """Пагинированный ответ со списком свойств."""
    items: List[Property] = Field(..., description="Список объектов недвижимости")
    total: int = Field(..., description="Общее количество результатов")
    skip: int = Field(..., description="Количество пропущенных записей")
    limit: int = Field(..., description="Максимальное количество записей в ответе")
    page: int = Field(..., description="Текущий номер страницы (1-indexed)")
    pages: int = Field(..., description="Общее количество страниц")
    has_next: bool = Field(..., description="Есть ли следующая страница")
    has_prev: bool = Field(..., description="Есть ли предыдущая страница")

    model_config = ConfigDict(from_attributes=True)