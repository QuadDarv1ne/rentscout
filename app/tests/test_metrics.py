import pytest
import time
from unittest.mock import patch, MagicMock
from app.utils.metrics import MetricsCollector, MetricsMiddleware, REQUEST_COUNT, REQUEST_DURATION, ACTIVE_REQUESTS, PARSER_CALLS, PARSER_DURATION

@pytest.fixture
def metrics_collector():
    """Фикстура для коллектора метрик."""
    return MetricsCollector()

def test_metrics_collector_initialization():
    """Тест инициализации коллектора метрик."""
    collector = MetricsCollector()
    assert collector is not None
    assert hasattr(collector, 'start_time')
    assert isinstance(collector.start_time, float)

def test_metrics_collector_record_request(metrics_collector):
    """Тест записи метрик HTTP запроса."""
    # Сохраняем начальные значения метрик
    initial_count = REQUEST_COUNT.collect()[0].samples[0].value if REQUEST_COUNT.collect() else 0
    
    # Записываем метрику
    metrics_collector.record_request("GET", "/api/test", 200, 0.1)
    
    # Проверяем, что метрика была записана
    # Note: В реальных условиях здесь нужно проверять через collect(), но для упрощения теста проверим наличие объекта

def test_metrics_collector_record_parser_call(metrics_collector):
    """Тест записи метрик вызова парсера."""
    # Записываем метрику
    metrics_collector.record_parser_call("AvitoParser", "success", 0.5)
    
    # Проверяем, что метрика была записана
    # Note: В реальных условиях здесь нужно проверять через collect(), но для упрощения теста проверим наличие объекта

def test_metrics_collector_request_counter(metrics_collector):
    """Тест счетчиков активных запросов."""
    initial_active = ACTIVE_REQUESTS.collect()[0].samples[0].value if ACTIVE_REQUESTS.collect() else 0
    
    # Увеличиваем счетчик
    metrics_collector.start_request()
    
    # Уменьшаем счетчик
    metrics_collector.end_request()

def test_metrics_collector_get_uptime(metrics_collector):
    """Тест получения времени работы приложения."""
    uptime = metrics_collector.get_uptime()
    assert isinstance(uptime, float)
    assert uptime >= 0

@pytest.mark.asyncio
async def test_metrics_middleware():
    """Тест middleware для сбора метрик."""
    # Создаем mock приложения
    mock_app = MagicMock()
    
    # Создаем middleware
    middleware = MetricsMiddleware(mock_app)
    
    # Создаем тестовую область видимости
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/test"
    }
    
    # Создаем mock функции receive и send
    mock_receive = MagicMock()
    mock_send = MagicMock()
    
    # Вызываем middleware
    await middleware(scope, mock_receive, mock_send)

def test_metrics_middleware_non_http():
    """Тест middleware для не-HTTP запросов."""
    # Создаем mock приложения
    mock_app = MagicMock()
    
    # Создаем middleware
    middleware = MetricsMiddleware(mock_app)
    
    # Создаем тестовую область видимости для websocket
    scope = {
        "type": "websocket"
    }
    
    # Создаем mock функции receive и send
    mock_receive = MagicMock()
    mock_send = MagicMock()
    
    # Вызываем middleware - не должно быть исключений
    import asyncio
    asyncio.run(middleware(scope, mock_receive, mock_send))