import pytest
import logging
from app.utils.logger import logger

def test_logger_instance():
    """Тест создания экземпляра логгера."""
    # Проверяем, что логгер создан
    assert logger is not None
    assert isinstance(logger, logging.Logger)
    
    # Проверяем имя логгера
    assert logger.name == "app.utils.logger"

def test_logger_level():
    """Тест уровня логгера."""
    # Проверяем, что уровень установлен на DEBUG
    assert logger.level == logging.DEBUG

def test_logger_handlers():
    """Тест обработчиков логгера."""
    # Проверяем, что есть хотя бы один обработчик
    assert len(logger.handlers) > 0
    
    # Проверяем, что есть обработчик консоли
    console_handler = None
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            console_handler = handler
            break
    
    assert console_handler is not None
    
    # Проверяем уровень обработчика
    assert console_handler.level == logging.DEBUG

def test_logger_formatter():
    """Тест форматировщика логгера."""
    # Находим обработчик консоли
    console_handler = None
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            console_handler = handler
            break
    
    assert console_handler is not None
    
    # Проверяем, что у обработчика есть форматировщик
    assert console_handler.formatter is not None
    
    # Проверяем формат строки
    expected_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    assert console_handler.formatter._fmt == expected_format

def test_logger_propagation():
    """Тест настройки propagation логгера."""
    # Проверяем, что propagation отключен
    assert logger.propagate is False

def test_logger_logging():
    """Тест возможности логгирования."""
    # Проверяем, что можно выполнить логгирование разных уровней
    logger.debug("Test debug message")
    logger.info("Test info message")
    logger.warning("Test warning message")
    logger.error("Test error message")
    logger.critical("Test critical message")
    
    # Если мы дошли до этого места, значит логгирование работает
    assert True