import pytest
from unittest.mock import AsyncMock, patch

from app.models.schemas import PropertyCreate
from app.services.search import SearchService


@pytest.fixture
def sample_properties():
    """Sample properties for testing."""
    return [
        PropertyCreate(
            source="avito",
            external_id="1",
            title="Квартира 1",
            price=3000.0,
            rooms=1,
            area=30.0,
            location=None,
            photos=[],
            description="Описание 1",
            link=None
        ),
        PropertyCreate(
            source="cian",
            external_id="2",
            title="Квартира 2",
            price=3500.0,
            rooms=2,
            area=50.0,
            location=None,
            photos=[],
            description="Описание 2",
            link=None
        ),
    ]


def test_search_service_initialization():
    """Тест инициализации сервиса поиска."""
    service = SearchService()
    # Now we have five parsers: Avito, Cian, Domofond, YandexRealty, and Domclick
    assert len(service.parsers) == 5
    parser_names = [parser.__class__.__name__ for parser in service.parsers]
    assert "AvitoParser" in parser_names
    assert "CianParser" in parser_names
    assert "DomofondParser" in parser_names
    assert "YandexRealtyParser" in parser_names
    assert "DomclickParser" in parser_names


@pytest.mark.asyncio
async def test_search_service_search_success(sample_properties):
    """Тест успешного поиска недвижимости."""
    service = SearchService()

    # Мокаем парсер
    mock_parser = AsyncMock()
    mock_parser.parse.return_value = sample_properties
    service.parsers = [mock_parser]

    # Мокаем save_properties
    with patch('app.services.search.save_properties') as mock_save:
        mock_save.return_value = None

        # Выполняем поиск
        results = await service.search("Москва", "Квартира")

        # Проверяем результаты
        assert len(results) == 2
        assert results[0].source == "avito"
        assert results[1].source == "cian"
        # Check that external_ids match the test data
        assert results[0].external_id == "1"
        assert results[1].external_id == "2"


@pytest.mark.asyncio
async def test_search_service_search_with_duplicates():
    """Тест поиска с дубликатами."""
    service = SearchService()

    # Мокаем парсеры с дублирующимися данными
    mock_parser1 = AsyncMock()
    mock_parser1.parse.return_value = [
        PropertyCreate(
            source="avito",
            external_id="1",
            title="Квартира 1",
            price=3000.0,
            rooms=1,
            area=30.0,
            location=None,
            photos=[],
            description="Описание 1",
            link=None
        )
    ]

    mock_parser2 = AsyncMock()
    mock_parser2.parse.return_value = [
        PropertyCreate(
            source="avito",  # Same source
            external_id="1",  # Same external_id - should be considered duplicate
            title="Квартира 1 (duplicate)",
            price=3100.0,
            rooms=1,
            area=30.0,
            location=None,
            photos=[],
            description="Описание 1 (duplicate)",
            link=None
        )
    ]

    service.parsers = [mock_parser1, mock_parser2]

    # Мокаем save_properties
    with patch('app.services.search.save_properties') as mock_save:
        mock_save.return_value = None

        # Выполняем поиск
        results = await service.search("Москва", "Квартира")

        # Проверяем, что дубликат был удален
        assert len(results) == 1
        assert results[0].source == "avito"
        assert results[0].external_id == "1"


@pytest.mark.asyncio
async def test_search_service_search_multiple_sources():
    """Тест поиска с несколькими источниками."""
    service = SearchService()

    # Мокаем несколько парсеров
    mock_parser1 = AsyncMock()
    mock_parser1.parse.return_value = [
        PropertyCreate(
            source="avito",
            external_id="1",
            title="Квартира 1",
            price=3000.0,
            rooms=1,
            area=30.0,
            location=None,
            photos=[],
            description="Описание 1",
            link=None
        )
    ]

    mock_parser2 = AsyncMock()
    mock_parser2.parse.return_value = [
        PropertyCreate(
            source="cian",
            external_id="2",
            title="Квартира 2",
            price=3500.0,
            rooms=2,
            area=50.0,
            location=None,
            photos=[],
            description="Описание 2",
            link=None
        )
    ]

    mock_parser3 = AsyncMock()
    mock_parser3.parse.return_value = [
        PropertyCreate(
            source="domofond",
            external_id="3",
            title="Квартира 3",
            price=2800.0,
            rooms=2,
            area=45.0,
            location=None,
            photos=[],
            description="Описание 3",
            link=None
        )
    ]

    mock_parser4 = AsyncMock()
    mock_parser4.parse.return_value = [
        PropertyCreate(
            source="yandex_realty",
            external_id="4",
            title="Квартира 4",
            price=3200.0,
            rooms=3,
            area=60.0,
            location=None,
            photos=[],
            description="Описание 4",
            link=None
        )
    ]

    mock_parser5 = AsyncMock()
    mock_parser5.parse.return_value = [
        PropertyCreate(
            source="domclick",
            external_id="5",
            title="Квартира 5",
            price=3100.0,
            rooms=2,
            area=48.0,
            location=None,
            photos=[],
            description="Описание 5",
            link=None
        )
    ]

    service.parsers = [mock_parser1, mock_parser2, mock_parser3, mock_parser4, mock_parser5]

    # Мокаем save_properties
    with patch('app.services.search.save_properties') as mock_save:
        mock_save.return_value = None

        # Выполняем поиск
        results = await service.search("Москва", "Квартира")

        # Проверяем, что результаты от всех парсеров возвращены
        assert len(results) == 5
        sources = [prop.source for prop in results]
        assert "avito" in sources
        assert "cian" in sources
        assert "domofond" in sources
        assert "yandex_realty" in sources
        assert "domclick" in sources