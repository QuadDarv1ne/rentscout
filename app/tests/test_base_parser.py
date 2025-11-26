import pytest
from app.parsers.base_parser import BaseParser
from app.models.schemas import PropertyCreate
from typing import List, Dict, Any

class MockParser(BaseParser):
    """Мock parser для тестирования базового класса."""
    
    async def parse(self, location: str, params: Dict[str, Any] = None) -> List[PropertyCreate]:
        # Создаем mock объект недвижимости
        property_data = {
            "source": "mock",
            "external_id": "12345",
            "title": "Тестовая квартира",
            "price": 1000.0,
            "rooms": 2,
            "area": 50.0,
            "photos": []
        }
        return [PropertyCreate(**property_data)]
    
    async def validate_params(self, params: Dict[str, Any]) -> bool:
        return True

@pytest.mark.asyncio
async def test_base_parser_instantiation():
    """Тест создания экземпляра парсера."""
    parser = MockParser()
    assert parser.name == "MockParser"

@pytest.mark.asyncio
async def test_base_parser_parse_method():
    """Тест абстрактного метода parse."""
    parser = MockParser()
    results = await parser.parse("Москва")
    assert len(results) == 1
    assert isinstance(results[0], PropertyCreate)
    assert results[0].source == "mock"
    assert results[0].title == "Тестовая квартира"

@pytest.mark.asyncio
async def test_base_parser_validate_params():
    """Тест метода валидации параметров."""
    parser = MockParser()
    result = await parser.validate_params({"test": "value"})
    assert result is True

@pytest.mark.asyncio
async def test_base_parser_preprocess_params():
    """Тест метода предобработки параметров."""
    parser = MockParser()
    params = {"test": "value"}
    processed = await parser.preprocess_params(params)
    assert processed == params

@pytest.mark.asyncio
async def test_base_parser_postprocess_results():
    """Тест метода постобработки результатов."""
    parser = MockParser()
    property_data = {
        "source": "mock",
        "external_id": "12345",
        "title": "Тестовая квартира",
        "price": 1000.0,
        "rooms": 2,
        "area": 50.0,
        "photos": []
    }
    results = [PropertyCreate(**property_data)]
    processed = await parser.postprocess_results(results)
    assert len(processed) == 1
    assert isinstance(processed[0], PropertyCreate)