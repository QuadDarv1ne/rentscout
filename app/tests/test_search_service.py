import pytest
from unittest.mock import patch, AsyncMock

from app.services.search import SearchService
from app.models.schemas import Property, PropertyCreate


@pytest.fixture
def sample_properties():
    """Фикстура с примерами объектов недвижимости."""
    return [
        PropertyCreate(
            source="avito",
            external_id="1",
            title="2-комн. квартира, 50 м²",
            price=3000.0,
            rooms=2,
            area=50.0,
            location=None,
            photos=[],
            description="Описание",
            link=None
        ),
        PropertyCreate(
            source="cian",
            external_id="2",
            title="1-комн. квартира, 35 м²",
            price=2500.0,
            rooms=1,
            area=35.0,
            location=None,
            photos=[],
            description="Описание",
            link=None
        )
    ]


@pytest.mark.asyncio
async def test_search_service_initialization():
    """Тест инициализации поискового сервиса."""
    service = SearchService()
    assert service is not None
    assert len(service.parsers) == 4  # Теперь у нас четыре парсера: Avito, Cian, Domofond и YandexRealty
    parser_names = [parser.__class__.__name__ for parser in service.parsers]
    assert "AvitoParser" in parser_names
    assert "CianParser" in parser_names
    assert "DomofondParser" in parser_names
    assert "YandexRealtyParser" in parser_names


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
        # Check that IDs are integers
        assert isinstance(results[0].id, int)
        assert isinstance(results[1].id, int)


@pytest.mark.asyncio
async def test_search_service_search_with_parser_error():
    """Тест поиска с ошибкой парсера."""
    service = SearchService()

    # Мокаем парсер, который выбрасывает исключение
    mock_parser1 = AsyncMock()
    mock_parser1.parse.side_effect = Exception("Parser error")

    # Мокаем второй парсер, который работает нормально
    mock_parser2 = AsyncMock()
    mock_parser2.parse.return_value = [
        PropertyCreate(
            source="cian",
            external_id="2",
            title="1-комн. квартира, 35 м²",
            price=2500.0,
            rooms=1,
            area=35.0,
            location=None,
            photos=[],
            description="Описание",
            link=None
        )
    ]

    service.parsers = [mock_parser1, mock_parser2]

    # Мокаем save_properties
    with patch('app.services.search.save_properties') as mock_save:
        mock_save.return_value = None

        # Выполняем поиск
        results = await service.search("Москва", "Квартира")

        # Проверяем, что результаты от второго парсера все еще возвращены
        assert len(results) == 1
        assert results[0].source == "cian"


@pytest.mark.asyncio
async def test_search_service_search_save_error():
    """Тест поиска с ошибкой сохранения."""
    service = SearchService()

    # Мокаем парсер
    mock_parser = AsyncMock()
    mock_parser.parse.return_value = [
        PropertyCreate(
            source="avito",
            external_id="1",
            title="2-комн. квартира, 50 м²",
            price=3000.0,
            rooms=2,
            area=50.0,
            location=None,
            photos=[],
            description="Описание",
            link=None
        )
    ]
    service.parsers = [mock_parser]

    # Мокаем save_properties, чтобы выбрасывал исключение
    with patch('app.services.search.save_properties') as mock_save:
        mock_save.side_effect = Exception("Save error")

        # Выполняем поиск - не должно выбрасывать исключение
        results = await service.search("Москва", "Квартира")

        # Проверяем, что результаты все еще возвращены
        assert len(results) == 1
        assert results[0].source == "avito"


@pytest.mark.asyncio
async def test_search_service_parallel_parsing():
    """Тест параллельного выполнения парсеров."""
    service = SearchService()

    # Создаем несколько моков парсеров
    mock_parser1 = AsyncMock()
    mock_parser1.parse.return_value = [
        PropertyCreate(
            source="avito",
            external_id="1",
            title="Квартира 1",
            price=3000.0,
            rooms=2,
            area=50.0,
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
            price=2500.0,
            rooms=1,
            area=35.0,
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

    service.parsers = [mock_parser1, mock_parser2, mock_parser3, mock_parser4]

    # Мокаем save_properties
    with patch('app.services.search.save_properties') as mock_save:
        mock_save.return_value = None

        # Выполняем поиск
        results = await service.search("Москва", "Квартира")

        # Проверяем, что результаты от всех парсеров возвращены
        assert len(results) == 4
        sources = [prop.source for prop in results]
        assert "avito" in sources
        assert "cian" in sources
        assert "domofond" in sources
        assert "yandex_realty" in sources