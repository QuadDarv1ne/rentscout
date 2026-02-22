"""
Тесты для схем валидации параметров парсеров.
"""

import pytest
from pydantic import ValidationError

from app.schemas.parser_params import (
    ParserParams,
    PropertyType,
    SortBy,
    SortOrder,
    LocationParams,
    PriceParams,
    PropertyFeaturesParams,
    create_parser_params,
)


class TestLocationParams:
    """Тесты валидации местоположения."""

    def test_valid_city(self):
        """Тест валидного города."""
        params = LocationParams(city="Москва")
        assert params.city == "Москва"

    def test_city_auto_title(self):
        """Тест автоматического приведения к title case."""
        params = LocationParams(city="москва")
        assert params.city == "Москва"

    def test_city_too_short(self):
        """Тест слишком короткого названия города."""
        with pytest.raises(ValidationError):
            LocationParams(city="М")

    def test_city_empty(self):
        """Тест пустого города."""
        with pytest.raises(ValidationError):
            LocationParams(city="")

    def test_city_whitespace(self):
        """Тест города с пробелами."""
        params = LocationParams(city="  москва  ")
        assert params.city == "Москва"

    def test_valid_district(self):
        """Тест валидного района."""
        params = LocationParams(city="Москва", district="Центральный")
        assert params.district == "Центральный"

    def test_coordinates_valid(self):
        """Тест валидных координат."""
        params = LocationParams(
            city="Москва",
            coordinates={"lat": 55.7558, "lon": 37.6173}
        )
        assert params.coordinates["lat"] == 55.7558
        assert params.coordinates["lon"] == 37.6173

    def test_coordinates_invalid_latitude(self):
        """Тест невалидной широты."""
        with pytest.raises(ValidationError):
            LocationParams(
                city="Москва",
                coordinates={"lat": 100, "lon": 37.6173}
            )

    def test_coordinates_invalid_longitude(self):
        """Тест невалидной долготы."""
        with pytest.raises(ValidationError):
            LocationParams(
                city="Москва",
                coordinates={"lat": 55.7558, "lon": 200}
            )


class TestPriceParams:
    """Тесты валидации цены."""

    def test_valid_price_range(self):
        """Тест валидного диапазона цен."""
        params = PriceParams(min_price=30000, max_price=100000)
        assert params.min_price == 30000
        assert params.max_price == 100000

    def test_price_min_greater_than_max(self):
        """Тест когда min больше max."""
        with pytest.raises(ValidationError):
            PriceParams(min_price=100000, max_price=30000)

    def test_price_negative(self):
        """Тест отрицательной цены."""
        with pytest.raises(ValidationError):
            PriceParams(min_price=-1000)

    def test_price_zero(self):
        """Тест нулевой цены."""
        params = PriceParams(min_price=0, max_price=0)
        assert params.min_price == 0
        assert params.max_price == 0

    def test_price_only_min(self):
        """Тест только минимальной цены."""
        params = PriceParams(min_price=30000)
        assert params.min_price == 30000
        assert params.max_price is None

    def test_price_only_max(self):
        """Тест только максимальной цены."""
        params = PriceParams(max_price=100000)
        assert params.max_price == 100000
        assert params.min_price is None

    def test_price_per_sqm(self):
        """Тест цены за кв.м."""
        params = PriceParams(max_price_per_sqm=200000)
        assert params.max_price_per_sqm == 200000


class TestPropertyFeaturesParams:
    """Тесты валидации характеристик недвижимости."""

    def test_valid_rooms_range(self):
        """Тест валидного диапазона комнат."""
        params = PropertyFeaturesParams(min_rooms=1, max_rooms=3)
        assert params.min_rooms == 1
        assert params.max_rooms == 3

    def test_rooms_min_greater_than_max(self):
        """Тест когда min комнат больше max."""
        with pytest.raises(ValidationError):
            PropertyFeaturesParams(min_rooms=3, max_rooms=1)

    def test_valid_area_range(self):
        """Тест валидного диапазона площади."""
        params = PropertyFeaturesParams(min_area=30, max_area=100)
        assert params.min_area == 30
        assert params.max_area == 100

    def test_area_min_greater_than_max(self):
        """Тест когда min площади больше max."""
        with pytest.raises(ValidationError):
            PropertyFeaturesParams(min_area=100, max_area=30)

    def test_valid_floor_range(self):
        """Тест валидного диапазона этажей."""
        params = PropertyFeaturesParams(min_floor=3, max_floor=10)
        assert params.min_floor == 3
        assert params.max_floor == 10

    def test_floor_min_greater_than_max(self):
        """Тест когда min этажа больше max."""
        with pytest.raises(ValidationError):
            PropertyFeaturesParams(min_floor=10, max_floor=3)

    def test_property_type_default(self):
        """Тест типа недвижимости по умолчанию."""
        params = PropertyFeaturesParams()
        assert params.property_type == PropertyType.APARTMENT

    def test_property_type_house(self):
        """Тест типа недвижимости - дом."""
        params = PropertyFeaturesParams(property_type=PropertyType.HOUSE)
        assert params.property_type == PropertyType.HOUSE

    def test_rooms_max_limit(self):
        """Тест максимального количества комнат."""
        with pytest.raises(ValidationError):
            PropertyFeaturesParams(max_rooms=11)


class TestParserParams:
    """Тесты основной схемы параметров."""

    def test_valid_full_params(self):
        """Тест полных валидных параметров."""
        params = ParserParams(
            city="Москва",
            district="Центральный",
            min_price=30000,
            max_price=100000,
            min_rooms=1,
            max_rooms=3,
            min_area=30,
            max_area=100,
            has_photos=True,
            sort_by=SortBy.PRICE,
            sort_order=SortOrder.ASC,
            limit=50
        )
        assert params.city == "Москва"
        assert params.min_price == 30000
        assert params.max_price == 100000
        assert params.has_photos is True
        assert params.sort_by == SortBy.PRICE
        assert params.limit == 50

    def test_minimal_params(self):
        """Тест минимальных параметров."""
        params = ParserParams(city="Москва")
        assert params.city == "Москва"
        assert params.property_type == PropertyType.APARTMENT

    def test_to_dict(self):
        """Тест конвертации в словарь."""
        params = ParserParams(
            city="Москва",
            min_price=30000,
            max_price=100000
        )
        result = params.to_dict()
        assert result["city"] == "Москва"
        assert result["min_price"] == 30000
        assert result["max_price"] == 100000
        assert "max_rooms" not in result  # None значения исключаются

    def test_extra_fields_allowed(self):
        """Тест разрешенных дополнительных полей."""
        params = ParserParams(
            city="Москва",
            custom_field="custom_value"
        )
        assert params.custom_field == "custom_value"

    def test_sort_by_enum(self):
        """Тест перечисления сортировки."""
        params = ParserParams(city="Москва", sort_by="price")
        assert params.sort_by == SortBy.PRICE

    def test_sort_order_enum(self):
        """Тест перечисления порядка сортировки."""
        params = ParserParams(city="Москва", sort_order="asc")
        assert params.sort_order == SortOrder.ASC


class TestCreateParserParams:
    """Тесты фабричной функции."""

    def test_avito_params(self):
        """Тест параметров для Avito."""
        params = create_parser_params(
            source="avito",
            city="Москва"
        )
        assert isinstance(params, ParserParams)

    def test_cian_params(self):
        """Тест параметров для Cian."""
        params = create_parser_params(
            source="cian",
            city="Санкт-Петербург"
        )
        assert params.city == "Санкт-Петербург"

    def test_unknown_source(self):
        """Тест неизвестного источника."""
        params = create_parser_params(
            source="unknown",
            city="Москва"
        )
        assert isinstance(params, ParserParams)
        assert params.city == "Москва"

    def test_case_insensitive_source(self):
        """Тест регистрационной независимости источника."""
        params1 = create_parser_params(source="AVITO", city="Москва")
        params2 = create_parser_params(source="avito", city="Москва")
        assert type(params1) == type(params2)


class TestFilterParams:
    """Тесты параметров фильтрации."""

    def test_has_photos(self):
        """Тест фильтра по фотографиям."""
        from app.schemas.parser_params import FilterParams
        
        params = FilterParams(has_photos=True)
        assert params.has_photos is True

    def test_features_list(self):
        """Тест списка удобств."""
        from app.schemas.parser_params import FilterParams
        
        params = FilterParams(features=["балкон", "парковка"])
        assert params.features == ["балкон", "парковка"]

    def test_source_filter(self):
        """Тест фильтра по источнику."""
        from app.schemas.parser_params import FilterParams
        
        params = FilterParams(source="avito")
        assert params.source == "avito"


class TestPaginationParams:
    """Тесты параметров пагинации."""

    def test_valid_pagination(self):
        """Тест валидной пагинации."""
        from app.schemas.parser_params import PaginationParams
        
        params = PaginationParams(skip=0, limit=50)
        assert params.skip == 0
        assert params.limit == 50

    def test_limit_max(self):
        """Тест максимального лимита."""
        from app.schemas.parser_params import PaginationParams
        
        with pytest.raises(ValidationError):
            PaginationParams(limit=101)

    def test_skip_negative(self):
        """Тест отрицательного skip."""
        from app.schemas.parser_params import PaginationParams
        
        with pytest.raises(ValidationError):
            PaginationParams(skip=-1)

    def test_default_values(self):
        """Тест значений по умолчанию."""
        from app.schemas.parser_params import PaginationParams
        
        params = PaginationParams()
        assert params.skip == 0
        assert params.limit == 100
