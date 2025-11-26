import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.parsers.base_parser import metrics_collector_decorator

class MockParser:
    """Мock парсер для тестирования декоратора."""
    
    def __init__(self):
        self.__class__.__name__ = "MockParser"
    
    @metrics_collector_decorator
    async def successful_method(self):
        """Метод, который успешно выполняется."""
        return "success"
    
    @metrics_collector_decorator
    async def failing_method(self):
        """Метод, который выбрасывает исключение."""
        raise Exception("Test error")

@pytest.mark.asyncio
async def test_metrics_decorator_success():
    """Тест декоратора метрик для успешного выполнения."""
    parser = MockParser()
    
    # Проверяем, что метод выполняется успешно
    result = await parser.successful_method()
    assert result == "success"

@pytest.mark.asyncio
async def test_metrics_decorator_exception():
    """Тест декоратора метрик для выполнения с исключением."""
    parser = MockParser()
    
    # Проверяем, что исключение пробрасывается
    with pytest.raises(Exception, match="Test error"):
        await parser.failing_method()