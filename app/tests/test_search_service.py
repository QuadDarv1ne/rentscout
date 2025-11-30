import pytest
from unittest.mock import patch, AsyncMock

from app.services.search import SearchService
from app.models.schemas import PropertyCreate


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
    assert len(service.parsers) == 2  # Теперь у нас два парсера: Avito и Cian
    parser_names = [parser.__class__.__name__ for parser in service.parsers]
    assert "AvitoParser" in parser_names
    assert "CianParser" in parser_names


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
        assert results[0].id == "avito_1"
        assert results[1].id == "cian_2"


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

    service.parsers = [mock_parser1, mock_parser2]

    # Мокаем save_properties
    with patch('app.services.search.save_properties') as mock_save:
        mock_save.return_value = None

        # Выполняем поиск
        results = await service.search("Москва", "Квартира")

        # Проверяем, что результаты от обоих парсеров возвращены
        assert len(results) == 2
        sources = [prop.source for prop in results]
        assert "avito" in sources
        assert "cian" in sources