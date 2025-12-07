import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from app.parsers.yandex_realty.parser import YandexRealtyParser
from app.models.schemas import PropertyCreate


@pytest.fixture
def yandex_realty_parser():
    return YandexRealtyParser()


@pytest.fixture
def mock_html_response():
    # Mock HTML response that simulates Yandex Realty search results page
    return """
    <html>
    <body>
        <div data-name="OfferCard">
            <div data-mark="OfferTitle">2-комн. квартира, 45 м², ЦАО</div>
            <div data-mark="MainPrice">120 000 ₽/мес.</div>
            <a href="/offer/123456789/">Ссылка</a>
            <div data-mark="Address">ул. Тверская, 10</div>
            <div data-mark="Description">Сдается 2-комнатная квартира в центре Москвы</div>
            <img src="photo1.jpg" />
            <img src="photo2.jpg" />
        </div>
        <div data-name="OfferCard">
            <div data-mark="OfferTitle">1-комн. квартира, 30 м², САО</div>
            <div data-mark="MainPrice">80 000 ₽/мес.</div>
            <a href="/offer/987654321/">Ссылка</a>
            <div data-mark="Address">пр. Ленина, 25</div>
            <div data-mark="Description">Сдается однокомнатная квартира рядом с метро</div>
            <img src="photo3.jpg" />
        </div>
    </body>
    </html>
    """


@pytest.mark.asyncio
async def test_yandex_realty_parser_initialization(yandex_realty_parser):
    """Test that YandexRealtyParser initializes correctly."""
    assert yandex_realty_parser.name == "YandexRealtyParser"
    assert yandex_realty_parser.BASE_URL == "https://realty.yandex.ru"


@pytest.mark.asyncio
async def test_yandex_realty_parser_validate_params(yandex_realty_parser):
    """Test parameter validation."""
    # Test with no params
    result = await yandex_realty_parser.validate_params(None)
    assert result is True
    
    # Test with empty params
    result = await yandex_realty_parser.validate_params({})
    assert result is True
    
    # Test with valid params
    result = await yandex_realty_parser.validate_params({"type": "квартира"})
    assert result is True


def test_yandex_realty_parser_build_query_params(yandex_realty_parser):
    """Test building query parameters."""
    # Test with Moscow
    params = yandex_realty_parser._build_query_params("Москва", {})
    assert params["region"] == "10933"
    assert params["category"] == "living"  # default
    
    # Test with Saint Petersburg
    params = yandex_realty_parser._build_query_params("Санкт-Петербург", {})
    assert params["region"] == "10935"
    
    # Test with property type
    params = yandex_realty_parser._build_query_params("Москва", {"type": "комната"})
    assert params["living_space"] == "room"
    
    # Test with price filters
    params = yandex_realty_parser._build_query_params("Москва", {"min_price": 10000, "max_price": 50000})
    assert params["priceMin"] == "10000"
    assert params["priceMax"] == "50000"
    
    # Test with room count
    params = yandex_realty_parser._build_query_params("Москва", {"rooms": 2})
    assert params["rooms"] == "2"


def test_yandex_realty_parser_extract_rooms_from_title(yandex_realty_parser):
    """Test extracting room count from title."""
    # Test various formats
    assert yandex_realty_parser._extract_rooms_from_title("2-к квартира") == 2
    assert yandex_realty_parser._extract_rooms_from_title("3 комнатная квартира") == 3
    assert yandex_realty_parser._extract_rooms_from_title("1 комн. квартира") == 1
    assert yandex_realty_parser._extract_rooms_from_title("Студия") is None  # No match


def test_yandex_realty_parser_extract_area_from_title(yandex_realty_parser):
    """Test extracting area from title."""
    # Test various formats
    assert yandex_realty_parser._extract_area_from_title("Квартира 45 м²") == 45.0
    assert yandex_realty_parser._extract_area_from_title("50 кв.м.") == 50.0
    assert yandex_realty_parser._extract_area_from_title("Квартира 30м2") == 30.0
    assert yandex_realty_parser._extract_area_from_title("Квартира без указания площади") is None


def test_yandex_realty_parser_extract_external_id(yandex_realty_parser):
    """Test extracting external ID from link."""
    link = "https://realty.yandex.ru/offer/123456789/"
    assert yandex_realty_parser._extract_external_id(link) == "123456789"
    
    # Test with invalid link
    assert yandex_realty_parser._extract_external_id("https://realty.yandex.ru/") == ""


@patch("httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_yandex_realty_parser_parse_success(mock_get, yandex_realty_parser, mock_html_response):
    """Test successful parsing of Yandex Realty search results."""
    # Setup mock response
    mock_response = Mock()
    mock_response.text = mock_html_response
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # Parse results
    results = await yandex_realty_parser.parse("Москва", {"type": "квартира"})
    
    # Check that we got results
    assert isinstance(results, list)
    assert len(results) == 2
    
    # Check first property
    prop1 = results[0]
    assert isinstance(prop1, PropertyCreate)
    assert prop1.source == "yandex_realty"
    assert prop1.title == "2-комн. квартира, 45 м², ЦАО"
    assert prop1.price == 120000.0
    assert prop1.rooms == 2
    assert prop1.area == 45.0
    assert prop1.link == "https://realty.yandex.ru/offer/123456789/"
    assert len(prop1.photos) == 2
    assert prop1.location is not None
    assert "address" in prop1.location
    assert prop1.location["address"] == "ул. Тверская, 10"
    
    # Check second property
    prop2 = results[1]
    assert isinstance(prop2, PropertyCreate)
    assert prop2.source == "yandex_realty"
    assert prop2.title == "1-комн. квартира, 30 м², САО"
    assert prop2.price == 80000.0
    assert prop2.rooms == 1
    assert prop2.area == 30.0
    assert prop2.link == "https://realty.yandex.ru/offer/987654321/"
    assert len(prop2.photos) == 1


@patch("httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_yandex_realty_parser_parse_http_error(mock_get, yandex_realty_parser):
    """Test handling of HTTP errors."""
    from app.utils.parser_errors import NetworkError
    from app.utils.retry import RetryError
    from httpx import HTTPStatusError
    
    # Setup mock to raise HTTP error
    mock_response = Mock()
    mock_response.status_code = 500
    mock_get.side_effect = HTTPStatusError("HTTP error", request=Mock(), response=mock_response)
    
    # Should raise RetryError (after 3 attempts) with NetworkError as cause
    with pytest.raises(RetryError):
        await yandex_realty_parser.parse("Москва", {"type": "квартира"})


if __name__ == "__main__":
    pytest.main([__file__])