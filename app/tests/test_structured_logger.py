"""Тесты для структурированного логирования."""

import pytest
import json
import logging
from io import StringIO

from app.utils.structured_logger import (
    setup_logger,
    StructuredLogger,
    JSONFormatter,
    set_correlation_id,
    get_correlation_id,
    clear_correlation_id,
)


def test_correlation_id_context():
    """Тест установки и получения correlation ID."""
    # Устанавливаем ID
    corr_id = set_correlation_id("test-123")
    assert corr_id == "test-123"
    
    # Получаем ID
    retrieved = get_correlation_id()
    assert retrieved == "test-123"
    
    # Очищаем
    clear_correlation_id()
    assert get_correlation_id() is None


def test_correlation_id_auto_generation():
    """Тест автогенерации correlation ID."""
    corr_id = set_correlation_id()
    assert corr_id is not None
    assert len(corr_id) > 0
    assert get_correlation_id() == corr_id
    
    clear_correlation_id()


def test_json_formatter():
    """Тест JSON форматирования логов."""
    # Создаем логгер с JSON форматтером
    logger = logging.getLogger("test_json")
    logger.setLevel(logging.DEBUG)
    
    # Создаем строковый буфер для вывода
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    # Логируем сообщение
    set_correlation_id("test-456")
    logger.info("Test message")
    
    # Получаем вывод
    output = stream.getvalue()
    log_data = json.loads(output.strip())
    
    # Проверяем структуру
    assert "timestamp" in log_data
    assert log_data["level"] == "INFO"
    assert log_data["message"] == "Test message"
    assert log_data["correlation_id"] == "test-456"
    assert "logger" in log_data
    assert "module" in log_data
    
    clear_correlation_id()
    logger.removeHandler(handler)


def test_json_formatter_with_exception():
    """Тест JSON форматирования с исключением."""
    logger = logging.getLogger("test_exception")
    logger.setLevel(logging.ERROR)
    
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    try:
        raise ValueError("Test error")
    except ValueError:
        logger.error("Error occurred", exc_info=True)
    
    output = stream.getvalue()
    log_data = json.loads(output.strip())
    
    assert "exception" in log_data
    assert log_data["exception"]["type"] == "ValueError"
    assert "Test error" in log_data["exception"]["message"]
    assert "traceback" in log_data["exception"]
    
    logger.removeHandler(handler)


def test_structured_logger():
    """Тест StructuredLogger."""
    base_logger = logging.getLogger("test_structured")
    base_logger.setLevel(logging.DEBUG)
    
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    base_logger.addHandler(handler)
    
    structured = StructuredLogger(base_logger)
    
    # Тестируем разные уровни
    structured.debug("Debug message")
    structured.info("Info message")
    structured.warning("Warning message")
    structured.error("Error message")
    
    output = stream.getvalue()
    assert "DEBUG: Debug message" in output
    assert "INFO: Info message" in output
    assert "WARNING: Warning message" in output
    assert "ERROR: Error message" in output
    
    base_logger.removeHandler(handler)


def test_structured_logger_request_logging():
    """Тест логирования запросов."""
    base_logger = logging.getLogger("test_request")
    base_logger.setLevel(logging.INFO)
    
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    base_logger.addHandler(handler)
    
    structured = StructuredLogger(base_logger)
    
    # Логируем запрос
    structured.log_request(
        method="GET",
        path="/api/properties",
        status_code=200,
        duration=0.123,
    )
    
    output = stream.getvalue()
    assert "GET" in output
    assert "/api/properties" in output
    assert "200" in output
    assert "0.123" in output
    
    base_logger.removeHandler(handler)


def test_structured_logger_parser_result():
    """Тест логирования результатов парсера."""
    base_logger = logging.getLogger("test_parser")
    base_logger.setLevel(logging.INFO)
    
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    base_logger.addHandler(handler)
    
    structured = StructuredLogger(base_logger)
    
    # Успешный парсинг
    structured.log_parser_result(
        source="avito",
        city="Москва",
        count=42,
        duration=1.5,
        success=True,
    )
    
    output = stream.getvalue()
    assert "avito" in output
    assert "Москва" in output
    assert "42" in output
    assert "✓" in output
    
    base_logger.removeHandler(handler)


def test_structured_logger_cache_operation():
    """Тест логирования операций с кешем."""
    base_logger = logging.getLogger("test_cache")
    base_logger.setLevel(logging.DEBUG)
    
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    base_logger.addHandler(handler)
    
    structured = StructuredLogger(base_logger)
    
    # Попадание в кеш
    structured.log_cache_operation(
        operation="get",
        hit=True,
        key="parser:avito:moscow",
    )
    
    output = stream.getvalue()
    assert "Cache get" in output
    assert "HIT" in output
    
    base_logger.removeHandler(handler)


def test_setup_logger():
    """Тест настройки логгера."""
    logger = setup_logger(name="test_setup", level="DEBUG", json_logs=False)
    
    assert logger.name == "test_setup"
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) > 0
    assert not logger.propagate
