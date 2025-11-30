import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from app.parsers.cian.parser import CianParser
from app.models.schemas import PropertyCreate


@pytest.fixture
def cian_parser():
    return CianParser()


@pytest.fixture
def mock_html_response():
    # Mock HTML response that simulates CIAN search results page
    return """
    <html>
    <body>
        <div data-name="CardComponent">
            <div data-name="Title">2-комн. квартира, 45 м², ЦАО</div>
            <div data-name="Price">120 000 ₽/мес.</div>
            <a href="/rent/flat/123456789/">Ссылка</a>
            <div data-name="AddressLine">ул. Тверская, 10</div>
            <div data-name="Description">Сдается 2-комнатная квартира в центре Москвы</div>
            <img src="photo1.jpg" />
            <img src="photo2.jpg" />
        </div>
        <div data-name="CardComponent">
            <div data-name="Title">1-комн. квартира, 30 м², САО</div>
            <div data-name="Price">80 000 ₽/мес.</div>
            <a href="/rent/flat/987654321/">Ссылка</a>
            <div data-name="AddressLine">пр. Ленина, 25</div>
            <div data-name="Description">Сдается однокомнатная квартира рядом с метро</div>
            <img src="photo3.jpg" />
        </div>
    </body>
    </html>
    """


@pytest.mark.asyncio
async def test_cian_parser_initialization(cian_parser):
    """Test that CianParser initializes correctly."""
    assert cian_parser.name == "CianParser"
    assert cian_parser.BASE_URL == "https://www.cian.ru"


@pytest.mark.asyncio
async def test_cian_parser_validate_params(cian_parser):
    """Test parameter validation."""
    # Test with no params
    result = await cian_parser.validate_params(None)
    assert result is True
    
    # Test with empty params
    result = await cian_parser.validate_params({})
    assert result is True
    
    # Test with valid params
    result = await cian_parser.validate_params({"type": "квартира"})
    assert result is True


def test_cian_parser_build_query_params(cian_parser):
    """Test building query parameters."""
    # Test with Moscow
    params = cian_parser._build_query_params("Москва", {})
    assert params["region"] == "1"
    assert params["type"] == "4"  # квартиры
    
    # Test with Saint Petersburg
    params = cian_parser._build_query_params("Санкт-Петербург", {})
    assert params["region"] == "2"
    
    # Test with property type
    params = cian_parser._build_query_params("Москва", {"type": "комната"})
    assert params["type"] == "5"  # комнаты
    
    # Test with price filters
    params = cian_parser._build_query_params("Москва", {"min_price": 10000, "max_price": 50000})
    assert params["price_min"] == "10000"
    assert params["price_max"] == "50000"
    
    # Test with room count
    params = cian_parser._build_query_params("Москва", {"rooms": 2})
    assert params["room"] == "2"


def test_cian_parser_extract_rooms_from_title(cian_parser):
    """Test extracting room count from title."""
    # Test various formats
    assert cian_parser._extract_rooms_from_title("2-к квартира") == 2
    assert cian_parser._extract_rooms_from_title("3 комнатная квартира") == 3
    assert cian_parser._extract_rooms_from_title("1 комн. квартира") == 1
    assert cian_parser._extract_rooms_from_title("Студия") is None  # No match


def test_cian_parser_extract_area_from_title(cian_parser):
    """Test extracting area from title."""
    # Test various formats
    assert cian_parser._extract_area_from_title("Квартира 45 м²") == 45.0
    assert cian_parser._extract_area_from_title("50 кв.м.") == 50.0
    assert cian_parser._extract_area_from_title("Квартира 30м2") == 30.0
    assert cian_parser._extract_area_from_title("Квартира без указания площади") is None


def test_cian_parser_extract_external_id(cian_parser):
    """Test extracting external ID from link."""
    link = "https://www.cian.ru/rent/flat/123456789/"
    assert cian_parser._extract_external_id(link) == "123456789"
    
    # Test with invalid link
    assert cian_parser._extract_external_id("https://www.cian.ru/") == ""


@patch("httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_cian_parser_parse_success(mock_get, cian_parser, mock_html_response):
    """Test successful parsing of CIAN search results."""
    # Setup mock response
    mock_response = Mock()
    mock_response.text = mock_html_response
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # Parse results
    results = await cian_parser.parse("Москва", {"type": "квартира"})
    
    # Check that we got results
    assert isinstance(results, list)
    assert len(results) == 2
    
    # Check first property
    prop1 = results[0]
    assert isinstance(prop1, PropertyCreate)
    assert prop1.source == "cian"
    assert prop1.title == "2-комн. квартира, 45 м², ЦАО"
    assert prop1.price == 120000.0
    assert prop1.rooms == 2
    assert prop1.area == 45.0
    assert prop1.link == "https://www.cian.ru/rent/flat/123456789/"
    assert len(prop1.photos) == 2
    assert prop1.location is not None
    assert "address" in prop1.location
    assert prop1.location["address"] == "ул. Тверская, 10"
    
    # Check second property
    prop2 = results[1]
    assert isinstance(prop2, PropertyCreate)
    assert prop2.source == "cian"
    assert prop2.title == "1-комн. квартира, 30 м², САО"
    assert prop2.price == 80000.0
    assert prop2.rooms == 1
    assert prop2.area == 30.0
    assert prop2.link == "https://www.cian.ru/rent/flat/987654321/"
    assert len(prop2.photos) == 1


@patch("httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_cian_parser_parse_http_error(mock_get, cian_parser):
    """Test handling of HTTP errors."""
    from app.utils.error_handler import NetworkError
    from httpx import HTTPStatusError
    
    # Setup mock to raise HTTP error
    mock_response = Mock()
    mock_response.status_code = 500
    mock_get.side_effect = HTTPStatusError("HTTP error", request=Mock(), response=mock_response)
    
    # Should raise NetworkError
    with pytest.raises(NetworkError):
        await cian_parser.parse("Москва", {"type": "квартира"})


if __name__ == "__main__":
    pytest.main([__file__])