from typing import List, Optional, Dict, Any

from app.models.schemas import PropertyCreate


class PropertyFilter:
    """Фильтр для свойств недвижимости с поддержкой различных критериев."""

    def __init__(
        self,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        min_rooms: Optional[int] = None,
        max_rooms: Optional[int] = None,
        min_area: Optional[float] = None,
        max_area: Optional[float] = None,
        property_type: Optional[str] = None,
        district: Optional[str] = None,
        has_photos: Optional[bool] = None,
        source: Optional[str] = None,
        max_price_per_sqm: Optional[float] = None,
        min_floor: Optional[int] = None,
        max_floor: Optional[int] = None,
        min_total_floors: Optional[int] = None,
        max_total_floors: Optional[int] = None,
        features: Optional[List[str]] = None,
        min_first_seen: Optional[str] = None,
        max_first_seen: Optional[str] = None,
        min_last_seen: Optional[str] = None,
        max_last_seen: Optional[str] = None,
        has_contact: Optional[bool] = None,
    ) -> None:
        """
        Инициализация фильтра.

        Args:
            min_price: Минимальная цена
            max_price: Максимальная цена
            min_rooms: Минимальное количество комнат
            max_rooms: Максимальное количество комнат
            min_area: Минимальная площадь
            max_area: Максимальная площадь
            property_type: Тип недвижимости
            district: Район
            has_photos: Наличие фотографий
            source: Источник
            max_price_per_sqm: Максимальная цена за квадратный метр
            min_floor: Минимальный этаж
            max_floor: Максимальный этаж
            min_total_floors: Минимальное количество этажей в здании
            max_total_floors: Максимальное количество этажей в здании
            features: Список обязательных характеристик (например, ["wifi", "parking"])
            min_first_seen: Минимальная дата первого появления (ISO format)
            max_first_seen: Максимальная дата первого появления (ISO format)
            min_last_seen: Минимальная дата последнего появления (ISO format)
            max_last_seen: Максимальная дата последнего появления (ISO format)
            has_contact: Наличие контактной информации
        """
        self.min_price: Optional[float] = min_price
        self.max_price: Optional[float] = max_price
        self.min_rooms: Optional[int] = min_rooms
        self.max_rooms: Optional[int] = max_rooms
        self.min_area: Optional[float] = min_area
        self.max_area: Optional[float] = max_area
        self.property_type: Optional[str] = property_type
        self.district: Optional[str] = district
        self.has_photos: Optional[bool] = has_photos
        self.source: Optional[str] = source
        self.max_price_per_sqm: Optional[float] = max_price_per_sqm
        self.min_floor: Optional[int] = min_floor
        self.max_floor: Optional[int] = max_floor
        self.min_total_floors: Optional[int] = min_total_floors
        self.max_total_floors: Optional[int] = max_total_floors
        self.features: Optional[List[str]] = features
        self.min_first_seen: Optional[str] = min_first_seen
        self.max_first_seen: Optional[str] = max_first_seen
        self.min_last_seen: Optional[str] = min_last_seen
        self.max_last_seen: Optional[str] = max_last_seen
        self.has_contact: Optional[bool] = has_contact

    def filter(self, properties: List[PropertyCreate]) -> List[PropertyCreate]:
        """
        Фильтрует список свойств согласно установленным критериям.

        Args:
            properties: Список свойств для фильтрации

        Returns:
            Отфильтрованный и отсортированный список свойств
        """
        filtered: List[PropertyCreate] = []
        for prop in properties:
            # Skip properties with invalid prices
            if prop.price <= 0:
                continue

            # Price filtering
            if self.min_price is not None and prop.price < self.min_price:
                continue
            if self.max_price is not None and prop.price > self.max_price:
                continue

            # Room filtering
            if self.min_rooms is not None and (prop.rooms is None or prop.rooms < self.min_rooms):
                continue
            if self.max_rooms is not None and (prop.rooms is None or prop.rooms > self.max_rooms):
                continue

            # Area filtering
            if self.min_area is not None and (prop.area is None or prop.area < self.min_area):
                continue
            if self.max_area is not None and (prop.area is None or prop.area > self.max_area):
                continue

            # Property type filtering (based on title)
            if self.property_type is not None and self.property_type.lower() not in prop.title.lower():
                continue

            # District filtering (based on title or location)
            if self.district is not None:
                district_found: bool = False
                # Проверяем в названии
                if self.district.lower() in prop.title.lower():
                    district_found = True
                # Проверяем в локации, если она есть
                elif prop.location and isinstance(prop.location, dict):
                    # Проверяем различные поля локации
                    for key, value in prop.location.items():
                        if isinstance(value, str) and self.district.lower() in value.lower():
                            district_found = True
                            break
                if not district_found:
                    continue

            # Photos filtering
            if self.has_photos is not None:
                has_photos: bool = len(prop.photos) > 0 if prop.photos else False
                if self.has_photos != has_photos:
                    continue

            # Source filtering
            if self.source is not None and prop.source.lower() != self.source.lower():
                continue

            # Price per square meter filtering
            if self.max_price_per_sqm is not None and prop.area and prop.area > 0:
                price_per_sqm = prop.price / prop.area
                if price_per_sqm > self.max_price_per_sqm:
                    continue

            filtered.append(prop)

        # Sort by price ascending and limit to 1000 results
        return sorted(filtered, key=lambda x: x.price)[:1000]
