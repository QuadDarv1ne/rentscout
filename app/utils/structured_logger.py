"""Структурированное JSON логирование с correlation IDs и контекстом."""

import logging
import json
import sys
import traceback
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

from app.core.config import settings

# ContextVar для хранения correlation ID в рамках запроса
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class JSONFormatter(logging.Formatter):
    """JSON форматтер для структурированных логов с метриками."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Форматирование лог записи в JSON с поддержкой метрик.
        
        Args:
            record: Запись лога
            
        Returns:
            JSON строка
        """
        # Базовые поля
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "application": "rentscout",
            "version": "1.2.0",
        }

        # Добавляем correlation ID если есть
        corr_id = correlation_id.get()
        if corr_id:
            log_data["correlation_id"] = corr_id

        # Добавляем информацию об исключении
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        
        # Добавляем контекст ошибки, если он есть
        if hasattr(record, "error_context"):
            log_data["error_context"] = record.error_context

        # Добавляем дополнительные поля из extra
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        # Добавляем поля из контекста (user_id, request_id и т.д.)
        for key in ["user_id", "request_id", "source", "city", "duration", "status_code"]:
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        return json.dumps(log_data, ensure_ascii=False)


class ContextualFormatter(logging.Formatter):
    """Читаемый форматтер с контекстом для разработки."""

    def format(self, record: logging.LogRecord) -> str:
        """Форматирование с читаемым выводом и цветами."""
        # Цветовые коды для уровней
        colors = {
            "DEBUG": "\033[36m",      # Cyan
            "INFO": "\033[32m",       # Green
            "WARNING": "\033[33m",    # Yellow
            "ERROR": "\033[31m",      # Red
            "CRITICAL": "\033[35m",   # Magenta
        }
        reset = "\033[0m"

        # Базовое форматирование
        from datetime import timezone
        level_color = colors.get(record.levelname, "")
        formatted = (
            f"{level_color}[{record.levelname}]{reset} "
            f"{datetime.now(timezone.utc).strftime('%H:%M:%S')} "
            f"{record.name}:{record.lineno} - "
            f"{record.getMessage()}"
        )

        # Добавляем correlation ID
        corr_id = correlation_id.get()
        if corr_id:
            formatted += f" [ID: {corr_id[:8]}]"

        # Добавляем информацию об исключении
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


def setup_logger(
    name: str = "rentscout",
    level: str = settings.LOG_LEVEL,
    json_logs: bool = False,
) -> logging.Logger:
    """
    Настройка логгера с поддержкой JSON и контекста.
    
    Args:
        name: Имя логгера
        level: Уровень логирования
        json_logs: Использовать JSON формат (для продакшена)
        
    Returns:
        Настроенный логгер
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))

    # Удаляем существующие обработчики
    logger.handlers.clear()

    # Создаем обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    # Выбираем форматтер
    if json_logs or settings.LOG_LEVEL == "PRODUCTION":
        formatter = JSONFormatter()
    else:
        formatter = ContextualFormatter()

    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Предотвращаем дублирование логов
    logger.propagate = False

    return logger


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """
    Установить correlation ID для текущего контекста.
    
    Args:
        corr_id: ID (если None, генерируется новый)
        
    Returns:
        Установленный correlation ID
    """
    if corr_id is None:
        corr_id = str(uuid.uuid4())
    correlation_id.set(corr_id)
    return corr_id


def get_correlation_id() -> Optional[str]:
    """Получить текущий correlation ID."""
    return correlation_id.get()


def clear_correlation_id():
    """Очистить correlation ID из контекста."""
    correlation_id.set(None)


class StructuredLogger:
    """Обертка для логгера с поддержкой структурированных данных."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def _log(
        self,
        level: int,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
        **kwargs,
    ):
        """Внутренний метод логирования."""
        extra = {"extra_data": extra_data} if extra_data else {}
        # Отфильтруем известные параметры logging
        for key, value in kwargs.items():
            if key not in ('exc_info', 'stack_info', 'stacklevel'):
                extra[key] = value
        self.logger.log(level, message, exc_info=exc_info, extra=extra)

    def debug(self, message: str, **kwargs):
        """Лог уровня DEBUG."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Лог уровня INFO."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Лог уровня WARNING."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Лог уровня ERROR."""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Лог уровня CRITICAL."""
        self._log(logging.CRITICAL, message, **kwargs)

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        **kwargs,
    ):
        """
        Логирование HTTP запроса.
        
        Args:
            method: HTTP метод
            path: Путь запроса
            status_code: Код ответа
            duration: Время выполнения в секундах
        """
        self.info(
            f"{method} {path} - {status_code} ({duration:.3f}s)",
            status_code=status_code,
            duration=duration,
            method=method,
            path=path,
            **kwargs,
        )

    def log_parser_result(
        self,
        source: str,
        city: str,
        count: int,
        duration: float,
        success: bool = True,
        error_message: Optional[str] = None,
        **kwargs,
    ):
        """
        Логирование результата парсера.
        
        Args:
            source: Источник (avito, cian и т.д.)
            city: Город
            count: Количество найденных объектов
            duration: Время выполнения
            success: Успешность парсинга
            error_message: Сообщение об ошибке (если есть)
        """
        level = logging.INFO if success else logging.WARNING
        message = (
            f"Parser {source} for {city}: "
            f"{'✓' if success else '✗'} {count} items ({duration:.2f}s)"
        )
        
        if error_message:
            message += f" | Error: {error_message}"
        
        self._log(
            level,
            message,
            source=source,
            city=city,
            count=count,
            duration=duration,
            success=success,
            error_message=error_message,
            **kwargs,
        )

    def log_cache_operation(
        self,
        operation: str,
        hit: bool,
        key: Optional[str] = None,
        size: Optional[int] = None,
        ttl: Optional[int] = None,
        **kwargs,
    ):
        """
        Логирование операции с кешем.
        
        Args:
            operation: Тип операции (get, set, delete)
            hit: Попадание в кеш
            key: Ключ кеша
            size: Размер данных (в байтах)
            ttl: Время жизни (в секундах)
        """
        message = f"Cache {operation}: {'HIT' if hit else 'MISS'}"
        if key:
            message += f" [{key[:50]}...]"
        if size:
            message += f" ({size} bytes)"
        if ttl:
            message += f" TTL: {ttl}s"

        level = logging.DEBUG if hit else logging.INFO
        self._log(
            level,
            message,
            operation=operation,
            hit=hit,
            key=key,
            size=size,
            ttl=ttl,
            **kwargs,
        )


# Создаем глобальный логгер
base_logger = setup_logger()
logger = StructuredLogger(base_logger)

# Для обратной совместимости экспортируем базовый логгер
__all__ = ["logger", "setup_logger", "StructuredLogger", "set_correlation_id", "get_correlation_id", "clear_correlation_id"]
