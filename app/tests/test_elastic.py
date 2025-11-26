import pytest
from unittest.mock import AsyncMock, patch
from app.db.elastic import es, index_property

def test_elasticsearch_client_instance():
    """Тест создания экземпляра клиента Elasticsearch."""
    # Проверяем, что клиент создан
    assert es is not None
    # Мы не можем напрямую проверить тип, так как это может быть mock в тестовой среде

@pytest.mark.asyncio
async def test_index_property():
    """Тест функции индексации свойства."""
    # Мокаем клиент Elasticsearch
    with patch('app.db.elastic.es') as mock_es:
        mock_es.index = AsyncMock()
        
        # Тестовые данные
        property_data = {
            "source": "avito",
            "external_id": "12345",
            "title": "Тестовая квартира",
            "price": 3000.0,
            "rooms": 2,
            "area": 50.0,
            "location": None,
            "photos": []
        }
        
        # Вызываем функцию
        await index_property(property_data)
        
        # Проверяем, что метод index был вызван с правильными аргументами
        mock_es.index.assert_called_once_with(
            index="properties",
            body=property_data,
            id="12345"
        )

@pytest.mark.asyncio
async def test_index_property_with_missing_external_id():
    """Тест функции индексации свойства с отсутствующим external_id."""
    # Мокаем клиент Elasticsearch
    with patch('app.db.elastic.es') as mock_es:
        mock_es.index = AsyncMock()
        
        # Тестовые данные без external_id
        property_data = {
            "source": "avito",
            "title": "Тестовая квартира",
            "price": 3000.0,
            "rooms": 2,
            "area": 50.0,
            "location": None,
            "photos": []
        }
        
        # Проверяем, что функция выбрасывает KeyError при отсутствии external_id
        with pytest.raises(KeyError):
            await index_property(property_data)

@pytest.mark.asyncio
async def test_index_property_elasticsearch_error():
    """Тест функции индексации свойства при ошибке Elasticsearch."""
    # Мокаем клиент Elasticsearch, чтобы он выбрасывал исключение
    with patch('app.db.elastic.es') as mock_es:
        mock_es.index = AsyncMock(side_effect=Exception("Elasticsearch error"))
        
        # Тестовые данные
        property_data = {
            "source": "avito",
            "external_id": "12345",
            "title": "Тестовая квартира",
            "price": 3000.0,
            "rooms": 2,
            "area": 50.0,
            "location": None,
            "photos": []
        }
        
        # Проверяем, что функция пробрасывает исключение
        with pytest.raises(Exception, match="Elasticsearch error"):
            await index_property(property_data)