import pytest

from app.models.schemas import PropertyCreate
from app.services.filter import PropertyFilter


@pytest.fixture
def sample_properties():
    """Фикстура с тестовыми данными недвижимости."""
    return [
        PropertyCreate(
            source="avito",
            external_id="1",
            title="2-комн. квартира в центре Москвы, 50 м²",
            price=3000.0,
            rooms=2,
            area=50.0,
            location={"district": "Центральный"},
            photos=["photo1.jpg", "photo2.jpg"],
        ),
        PropertyCreate(
            source="cian",
            external_id="2",
            title="1-комн. квартира в районе Хамовники, 35 м²",
            price=2500.0,
            rooms=1,
            area=35.0,
            location={"district": "ЮЗАО"},
            photos=[],
        ),
        PropertyCreate(
            source="avito",
            external_id="3",
            title="3-комн. квартира в районе Перово, 70 м²",
            price=4000.0,
            rooms=3,
            area=70.0,
            location={"district": "ВАО"},
            photos=["photo3.jpg"],
        ),
        PropertyCreate(
            source="ostrovok",
            external_id="4",
            title="Студия в районе Кунцево, 25 м²",
            price=2000.0,
            rooms=None,
            area=25.0,
            location={"district": "ЗАО"},
            photos=["photo4.jpg", "photo5.jpg"],
        ),
    ]


def test_filter_by_district(sample_properties):
    """Тест фильтрации по району."""
    property_filter = PropertyFilter(district="центр")
    filtered = property_filter.filter(sample_properties)
    assert len(filtered) == 1
    assert "центре" in filtered[0].title.lower()


def test_filter_by_has_photos(sample_properties):
    """Тест фильтрации по наличию фотографий."""
    # Фильтр: только объявления с фото
    property_filter = PropertyFilter(has_photos=True)
    filtered = property_filter.filter(sample_properties)
    assert len(filtered) == 3
    for prop in filtered:
        assert len(prop.photos) > 0

    # Фильтр: только объявления без фото
    property_filter = PropertyFilter(has_photos=False)
    filtered = property_filter.filter(sample_properties)
    assert len(filtered) == 1
    assert len(filtered[0].photos) == 0


def test_filter_by_source(sample_properties):
    """Тест фильтрации по источнику."""
    property_filter = PropertyFilter(source="avito")
    filtered = property_filter.filter(sample_properties)
    assert len(filtered) == 2
    for prop in filtered:
        assert prop.source == "avito"


def test_filter_by_price_per_sqm(sample_properties):
    """Тест фильтрации по цене за квадратный метр."""
    # Максимальная цена за квадратный метр: 60 руб./м²
    # Проверяем, что отсеиваются объявления с большей ценой за м²
    property_filter = PropertyFilter(max_price_per_sqm=60.0)
    filtered = property_filter.filter(sample_properties)

    # Рассчитаем цену за м² для каждого объявления:
    # 1. 3000/50 = 60 (проходит)
    # 2. 2500/35 ≈ 71.4 (не проходит)
    # 3. 4000/70 ≈ 57.1 (проходит)
    # 4. 2000/25 = 80 (не проходит)

    assert len(filtered) == 2
    # Проверяем, что остались только объявления с подходящей ценой за м²
    for prop in filtered:
        price_per_sqm = prop.price / prop.area
        assert price_per_sqm <= 60.0


def test_combined_filters(sample_properties):
    """Тест комбинированной фильтрации."""
    # Комбинируем несколько фильтров:
    # 1. Источник: avito
    # 2. Наличие фото: True
    # 3. Район: содержит "перово"

    property_filter = PropertyFilter(source="avito", has_photos=True, district="перово")

    filtered = property_filter.filter(sample_properties)
    assert len(filtered) == 1
    assert filtered[0].source == "avito"
    assert len(filtered[0].photos) > 0
    assert "перово" in filtered[0].title.lower()


def test_no_filters(sample_properties):
    """Тест без фильтров."""
    property_filter = PropertyFilter()
    filtered = property_filter.filter(sample_properties)
    assert len(filtered) == 4  # Все объявления должны пройти


def test_all_filters(sample_properties):
    """Тест со всеми фильтрами."""
    property_filter = PropertyFilter(
        min_price=2000.0,
        max_price=4000.0,
        min_rooms=1,
        max_rooms=3,
        min_area=30.0,
        max_area=70.0,
        property_type="квартира",
        district="центр",
        has_photos=True,
        source="avito",
        max_price_per_sqm=70.0,
    )

    filtered = property_filter.filter(sample_properties)
    # Только первое объявление должно пройти все фильтры:
    # - Цена: 3000 (в диапазоне 2000-4000)
    # - Комнаты: 2 (в диапазоне 1-3)
    # - Площадь: 50 (в диапазоне 30-70)
    # - Тип: содержит "квартира"
    # - Район: содержит "центр"
    # - Есть фото: да
    # - Источник: avito
    # - Цена за м²: 60 (меньше 70)

    assert len(filtered) == 1
    assert filtered[0].external_id == "1"
