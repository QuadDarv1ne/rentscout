import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from app.parsers.domclick.parser import DomclickParser
from app.models.schemas import PropertyCreate


@pytest.fixture
def domclick_parser():
    return DomclickParser()


@pytest.fixture
def mock_html_response():
    # Mock HTML response that simulates DomClick search results page
    return """
    <html>
    <body>
        <div data-testid="search-results-item">
            <div data-testid="item-title">2-комн. квартира, 45 м², ЦАО</div>
            <div data-testid="item-price">120 000 ₽/мес.</div>
            <a href="/listing/123456789/">Ссылка</a>
            <div data-testid="item-address">ул. Тверская, 10</div>
            <div data-testid="item-description">Сдается 2-комнатная квартира в центре Москвы</div>
            <img src="photo1.jpg" />
            <img src="photo2.jpg" />
        </div>
        <div data-testid="search-results-item">
            <div data-testid="item-title">1-комн. квартира, 30 м², САО</div>
            <div data-testid="item-price">80 000 ₽/мес.</div>
            <a href="/listing/987654321/">Ссылка</a>
            <div data-testid="item-address">пр. Ленина, 25</div>
            <div data-testid="item-description">Сдается однокомнатная квартира рядом с метро</div>
            <img src="photo3.jpg" />
        </div>
    </body>
    </html>
    """


@pytest.mark.asyncio
async def test_domclick_parser_initialization(domclick_parser):
    """Test that DomclickParser initializes correctly."""
    assert domclick_parser.name == "DomclickParser"
    assert domclick_parser.BASE_URL == "https://domclick.ru"


@pytest.mark.asyncio
async def test_domclick_parser_validate_params(domclick_parser):
    """Test parameter validation."""
    # Test with no params
    result = await domclick_parser.validate_params(None)
    assert result is True
    
    # Test with empty params
    result = await domclick_parser.validate_params({})
    assert result is True
    
    # Test with valid params
    result = await domclick_parser.validate_params({"type": "квартира"})
    assert result is True


def test_domclick_parser_convert_location_to_slug(domclick_parser):
    """Test converting location names to slugs."""
    # Test Moscow
    assert domclick_parser._convert_location_to_slug("Москва") == "moskva"
    assert domclick_parser._convert_location_to_slug("moscow") == "moskva"
    
    # Test Saint Petersburg
    assert domclick_parser._convert_location_to_slug("Санкт-Петербург") == "sankt-peterburg"
    assert domclick_parser._convert_location_to_slug("spb") == "sankt-peterburg"
    
    # Test unknown location (should return as-is)
    assert domclick_parser._convert_location_to_slug("Казань") == "казань"


def test_domclick_parser_build_query_params(domclick_parser):
    """Test building query parameters."""
    # Test with Moscow
    params = domclick_parser._build_query_params({
        "min_price": 30000,
        "max_price": 100000,
        "rooms": 2,
        "min_area": 30,
        "max_area": 100
    })
    
    assert params["priceMin"] == "30000"
    assert params["priceMax"] == "100000"
    assert params["room"] == "2"
    assert params["areaMin"] == "30"
    assert params["areaMax"] == "100"


@patch("httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_domclick_parser_parse_success(mock_get, domclick_parser, mock_html_response):
    """Test successful parsing of DomClick search results."""
    # Setup mock response
    mock_response = Mock()
    mock_response.text = mock_html_response
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # Parse results
    results = await domclick_parser.parse("Москва", {"type": "квартира"})
    
    # Check that we got results
    assert isinstance(results, list)
    assert len(results) == 2
    
    # Check first property
    prop1 = results[0]
    assert isinstance(prop1, PropertyCreate)
    assert prop1.source == "domclick"
    assert prop1.title == "2-комн. квартира, 45 м², ЦАО"
    assert prop1.price == 120000.0
    assert prop1.rooms == 2
    assert prop1.area == 45.0
    assert prop1.link == "https://domclick.ru/listing/123456789/"
    assert len(prop1.photos) == 2
    assert prop1.location is not None
    assert "address" in prop1.location
    assert prop1.location["address"] == "ул. Тверская, 10"
    
    # Check second property
    prop2 = results[1]
    assert isinstance(prop2, PropertyCreate)
    assert prop2.source == "domclick"
    assert prop2.title == "1-комн. квартира, 30 м², САО"
    assert prop2.price == 80000.0
    assert prop2.rooms == 1
    assert prop2.area == 30.0


@patch("httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_domclick_parser_parse_empty_results(mock_get, domclick_parser):
    """Test parsing when no results are found."""
    # Setup mock response with no results
    mock_response = Mock()
    mock_response.text = "<html><body></body></html>"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # Parse results
    results = await domclick_parser.parse("Москва", {"type": "квартира"})
    
    # Should return empty list
    assert isinstance(results, list)
    assert len(results) == 0