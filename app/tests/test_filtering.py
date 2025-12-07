import pytest

from app.models.schemas import PropertyCreate
from app.services.filter import PropertyFilter


def test_property_filter_basic():
    """Test basic property filtering functionality."""
    # Create test properties
    properties = [
        PropertyCreate(source="avito", external_id="1", title="1-комн. квартира, 30 м²", price=3000, rooms=1, area=30),
        PropertyCreate(source="avito", external_id="2", title="2-комн. квартира, 45 м²", price=4500, rooms=2, area=45),
        PropertyCreate(source="avito", external_id="3", title="3-комн. квартира, 60 м²", price=6000, rooms=3, area=60),
    ]

    # Test basic filtering
    filter_obj = PropertyFilter(min_price=3500, max_price=5000)
    filtered, total = filter_obj.filter(properties)

    assert len(filtered) == 1
    assert total == 1
    assert filtered[0].external_id == "2"
    assert filtered[0].price == 4500


def test_property_filter_rooms():
    """Test room-based filtering."""
    properties = [
        PropertyCreate(source="avito", external_id="1", title="Студия, 25 м²", price=2500, rooms=0, area=25),
        PropertyCreate(source="avito", external_id="2", title="1-комн. квартира, 30 м²", price=3000, rooms=1, area=30),
        PropertyCreate(source="avito", external_id="3", title="2-комн. квартира, 45 м²", price=4500, rooms=2, area=45),
    ]

    # Test room filtering
    filter_obj = PropertyFilter(min_rooms=1, max_rooms=2)
    filtered = filter_obj.filter(properties)

    assert len(filtered) == 2
    assert filtered[0].external_id == "2"
    assert filtered[1].external_id == "3"


def test_property_filter_area():
    """Test area-based filtering."""
    properties = [
        PropertyCreate(
            source="avito", external_id="1", title="Маленькая квартира, 20 м²", price=2000, rooms=1, area=20
        ),
        PropertyCreate(source="avito", external_id="2", title="Средняя квартира, 40 м²", price=4000, rooms=2, area=40),
        PropertyCreate(source="avito", external_id="3", title="Большая квартира, 60 м²", price=6000, rooms=3, area=60),
    ]

    # Test area filtering
    filter_obj = PropertyFilter(min_area=25, max_area=50)
    filtered = filter_obj.filter(properties)

    assert len(filtered) == 1
    assert filtered[0].external_id == "2"
    assert filtered[0].area == 40


def test_property_filter_type():
    """Test property type filtering based on title."""
    properties = [
        PropertyCreate(source="avito", external_id="1", title="1-комн. квартира, 30 м²", price=3000, rooms=1, area=30),
        PropertyCreate(source="avito", external_id="2", title="2-комн. квартира, 45 м²", price=4500, rooms=2, area=45),
        PropertyCreate(source="avito", external_id="3", title="Студия, 20 м²", price=2000, rooms=0, area=20),
    ]

    # Test property type filtering
    filter_obj = PropertyFilter(property_type="квартира")
    filtered = filter_obj.filter(properties)

    assert len(filtered) == 2
    assert filtered[0].external_id == "1"
    assert filtered[1].external_id == "2"


def test_property_filter_combined():
    """Test combined filtering with multiple criteria."""
    properties = [
        PropertyCreate(source="avito", external_id="1", title="1-комн. квартира, 30 м²", price=3000, rooms=1, area=30),
        PropertyCreate(source="avito", external_id="2", title="2-комн. квартира, 45 м²", price=4500, rooms=2, area=45),
        PropertyCreate(source="avito", external_id="3", title="2-комн. квартира, 50 м²", price=5000, rooms=2, area=50),
        PropertyCreate(source="avito", external_id="4", title="3-комн. квартира, 60 м²", price=6000, rooms=3, area=60),
    ]

    # Test combined filtering
    filter_obj = PropertyFilter(min_price=4000, max_price=5500, min_rooms=2, max_rooms=2, min_area=40, max_area=55)
    filtered = filter_obj.filter(properties)

    assert len(filtered) == 2
    assert filtered[0].external_id == "2"
    assert filtered[1].external_id == "3"
