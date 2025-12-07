import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from app.parsers.domofond.parser import DomofondParser
from app.models.schemas import PropertyCreate


@pytest.fixture
def domofond_parser():
    return DomofondParser()


@pytest.fixture
def mock_html_response():
    # Mock HTML response that simulates Domofond search results page
    return """
    <html>
    <body>
        <div class="listing-item">
            <div class="listing-title">2-комн. квартира, 45 м², ЦАО</div>
            <div class="listing-price">120 000 ₽/мес.</div>
            <a href="/listing/123456789/">Ссылка</a>
            <div class="listing-address">ул. Тверская, 10</div>
            <div class="listing-description">Сдается 2-комнатная квартира в центре Москвы</div>
            <img src="photo1.jpg" />
            <img src="photo2.jpg" />
        </div>
        <div class="listing-item">
            <div class="listing-title">1-комн. квартира, 30 м², САО</div>
            <div class="listing-price">80 000 ₽/мес.</div>
            <a href="/listing/987654321/">Ссылка</a>
            <div class="listing-address">пр. Ленина, 25</div>
            <div class="listing-description">Сдается однокомнатная квартира рядом с метро</div>
            <img src="photo3.jpg" />
        </div>
    </body>
    </html>
    """


@pytest.mark.asyncio
async def test_domofond_parser_initialization(domofond_parser):
    """Test that DomofondParser initializes correctly."""
    assert domofond_parser.name == "DomofondParser"
    assert domofond_parser.BASE_URL == "https://domofond.ru"


@pytest.mark.asyncio
async def test_domofond_parser_validate_params(domofond_parser):
    """Test parameter validation."""
    # Test with no params
    result = await domofond_parser.validate_params(None)
    assert result is True
    
    # Test with empty params
    result = await domofond_parser.validate_params({})
    assert result is True
    
    # Test with valid params
    result = await domofond_parser.validate_params({"type": "квартира"})
    assert result is True


def test_domofond_parser_build_query_params(domofond_parser):
    """Test building query parameters."""
    # Test with price filters
    params = domofond_parser._build_query_params({"min_price": 10000, "max_price": 50000})
    assert params["MinPrice"] == "10000"
    assert params["MaxPrice"] == "50000"
    
    # Test with room count
    params = domofond_parser._build_query_params({"rooms": 2})
    assert params["RoomsCount"] == "2"


def test_domofond_parser_extract_rooms_from_title(domofond_parser):
    """Test extracting room count from title."""
    # Test various formats
    assert domofond_parser._extract_rooms_from_title("2-к квартира") == 2
    assert domofond_parser._extract_rooms_from_title("3 комнатная квартира") == 3
    assert domofond_parser._extract_rooms_from_title("1 комн. квартира") == 1
    assert domofond_parser._extract_rooms_from_title("Студия") is None  # No match


def test_domofond_parser_extract_area_from_title(domofond_parser):
    """Test extracting area from title."""
    # Test various formats
    assert domofond_parser._extract_area_from_title("Квартира 45 м²") == 45.0
    assert domofond_parser._extract_area_from_title("50 кв.м.") == 50.0
    assert domofond_parser._extract_area_from_title("Квартира 30м2") == 30.0
    assert domofond_parser._extract_area_from_title("Квартира без указания площади") is None


def test_domofond_parser_extract_external_id(domofond_parser):
    """Test extracting external ID from link."""
    link = "https://domofond.ru/listing/123456789/"
    assert domofond_parser._extract_external_id(link) == "123456789"
    
    # Test with invalid link
    assert domofond_parser._extract_external_id("https://domofond.ru/") == ""


@patch("httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_domofond_parser_parse_success(mock_get, domofond_parser, mock_html_response):
    """Test successful parsing of Domofond search results."""
    # Setup mock response
    mock_response = Mock()
    mock_response.text = mock_html_response
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    
    # Parse results
    results = await domofond_parser.parse("Москва", {"type": "квартира"})
    
    # Check that we got results
    assert isinstance(results, list)
    assert len(results) == 2
    
    # Check first property
    prop1 = results[0]
    assert isinstance(prop1, PropertyCreate)
    assert prop1.source == "domofond"
    assert prop1.title == "2-комн. квартира, 45 м², ЦАО"
    assert prop1.price == 120000.0
    assert prop1.rooms == 2
    assert prop1.area == 45.0
    assert prop1.link == "https://domofond.ru/listing/123456789/"
    assert len(prop1.photos) == 2
    assert prop1.location is not None
    assert "address" in prop1.location
    assert prop1.location["address"] == "ул. Тверская, 10"
    
    # Check second property
    prop2 = results[1]
    assert isinstance(prop2, PropertyCreate)
    assert prop2.source == "domofond"
    assert prop2.title == "1-комн. квартира, 30 м², САО"
    assert prop2.price == 80000.0
    assert prop2.rooms == 1
    assert prop2.area == 30.0
    assert prop2.link == "https://domofond.ru/listing/987654321/"
    assert len(prop2.photos) == 1


@patch("httpx.AsyncClient.get")
@pytest.mark.asyncio
async def test_domofond_parser_parse_http_error(mock_get, domofond_parser):
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
        await domofond_parser.parse("Москва", {"type": "квартира"})


if __name__ == "__main__":
    pytest.main([__file__])