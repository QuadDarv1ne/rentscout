import pytest

from app.parsers.avito.parser import AvitoParser


def test_extract_rooms_from_title():
    """Test extraction of room count from property titles."""
    parser = AvitoParser()

    # Test various room formats
    assert parser._extract_rooms_from_title("1-к квартира") == 1
    assert parser._extract_rooms_from_title("2 комнатная квартира") == 2
    assert parser._extract_rooms_from_title("3 комн. квартира") == 3
    assert parser._extract_rooms_from_title("Студия") is None  # No room count


def test_extract_area_from_title():
    """Test extraction of area from property titles."""
    parser = AvitoParser()

    # Test various area formats
    assert parser._extract_area_from_title("Квартира 30 м²") == 30.0
    assert parser._extract_area_from_title("Квартира 45.5 м2") == 45.5
    assert parser._extract_area_from_title("Квартира 50 кв. м") == 50.0
    assert parser._extract_area_from_title("Квартира 55.7 кв.м") == 55.7
    assert parser._extract_area_from_title("Квартира без указания площади") is None  # No area


def test_extract_location():
    """Test extraction of location information."""
    parser = AvitoParser()

    # Create a mock item with location in title
    from bs4 import BeautifulSoup

    html = """
    <div data-marker="item" data-item-id="12345">
        <h3 itemprop="name">2-к квартира в районе Хамовники, 45 м²</h3>
        <span itemprop="price" content="4500">4 500 ₽/мес.</span>
        <a data-marker="item-title" href="/moskva/kvartiry/12345">Подробнее</a>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("[data-marker='item']")

    location = parser._extract_location(item)
    assert location is not None
    assert "district" in location
    assert "хамовники" in location["district"].lower()


def test_extract_description():
    """Test extraction of description."""
    parser = AvitoParser()

    # Create a mock item with description
    from bs4 import BeautifulSoup

    html = """
    <div data-marker="item" data-item-id="12345">
        <h3 itemprop="name">2-к квартира, 45 м²</h3>
        <span itemprop="price" content="4500">4 500 ₽/мес.</span>
        <a data-marker="item-title" href="/moskva/kvartiry/12345">Подробнее</a>
        <div>Уютная квартира в центре Москвы. Современный ремонт, вся необходимая мебель.</div>
    </div>
    """
    soup = BeautifulSoup(html, "lxml")
    item = soup.select_one("[data-marker='item']")

    description = parser._extract_description(item)
    assert description is not None
    assert "Уютная квартира" in description


def test_parse_html_basic():
    """Test basic HTML parsing functionality."""
    parser = AvitoParser()

    # Simple HTML test case
    html = """
    <div data-marker="item" data-item-id="12345">
        <h3 itemprop="name">2-к квартира, 45 м²</h3>
        <span itemprop="price" content="4500">4 500 ₽/мес.</span>
        <a data-marker="item-title" href="/moskva/kvartiry/12345">Подробнее</a>
    </div>
    """

    properties = parser._parse_html(html)

    assert len(properties) == 1
    prop = properties[0]
    assert prop.source == "avito"
    assert prop.external_id == "12345"
    assert prop.title == "2-к квартира, 45 м²"
    assert prop.price == 4500.0
    assert prop.rooms == 2
    assert prop.area == 45.0


def test_parse_html_multiple_items():
    """Test parsing multiple items from HTML."""
    parser = AvitoParser()

    # HTML with multiple items
    html = """
    <div data-marker="item" data-item-id="12345">
        <h3 itemprop="name">1-к квартира, 30 м²</h3>
        <span itemprop="price" content="3000">3 000 ₽/мес.</span>
        <a data-marker="item-title" href="/moskva/kvartiry/12345">Подробнее</a>
    </div>
    <div data-marker="item" data-item-id="67890">
        <h3 itemprop="name">2-к квартира, 45 м²</h3>
        <span itemprop="price" content="4500">4 500 ₽/мес.</span>
        <a data-marker="item-title" href="/moskva/kvartiry/67890">Подробнее</a>
    </div>
    """

    properties = parser._parse_html(html)

    assert len(properties) == 2
    assert properties[0].external_id == "12345"
    assert properties[1].external_id == "67890"
    assert properties[0].rooms == 1
    assert properties[1].rooms == 2
    assert properties[0].area == 30.0
    assert properties[1].area == 45.0


def test_parse_html_with_photos():
    """Test parsing items with photos."""
    parser = AvitoParser()

    # HTML with photo elements
    html = """
    <div data-marker="item" data-item-id="12345">
        <h3 itemprop="name">2-к квартира, 45 м²</h3>
        <span itemprop="price" content="4500">4 500 ₽/мес.</span>
        <a data-marker="item-title" href="/moskva/kvartiry/12345">Подробнее</a>
        <img src="https://example.com/photo1.jpg" alt="Фото 1">
        <img src="https://example.com/photo2.jpg" alt="Фото 2">
    </div>
    """

    properties = parser._parse_html(html)

    assert len(properties) == 1
    prop = properties[0]
    assert len(prop.photos) == 2
    assert "https://example.com/photo1.jpg" in prop.photos
    assert "https://example.com/photo2.jpg" in prop.photos
