"""Улучшенная обработка ошибок парсеров с специфичными типами и обработками."""

import asyncio
import logging
from enum import Enum
from typing import Any, Callable, Optional, Tuple, Type

from app.utils.logger import logger

# ============================================================================
# Пользовательские исключения парсеров
# ============================================================================


class ParserException(Exception):
    """Базовое исключение для всех ошибок парсеров."""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        self.message = message
        self.original_exception = original_exception
        super().__init__(message)


class NetworkError(ParserException):
    """Ошибка сети - временная, требует повтора."""

    pass


class RateLimitError(NetworkError):
    """Ошибка превышения rate limit - требует больной задержки перед повтором."""

    pass


class TimeoutError(NetworkError):
    """Ошибка timeout - требует повтора с увеличенной задержкой."""

    pass


class ParsingError(ParserException):
    """Ошибка парсинга - обычно постоянная, не требует повтора."""

    pass


class ValidationError(ParserException):
    """Ошибка валидации данных - постоянная, не требует повтора."""

    pass


class AuthenticationError(ParserException):
    """Ошибка аутентификации - требует исправления конфигурации."""

    pass


class SourceUnavailableError(NetworkError):
    """Источник недоступен (503, 404) - требует повтора позже."""

    pass


# ============================================================================
# Классификация ошибок
# ============================================================================


class ErrorSeverity(str, Enum):
    """Уровень серьезности ошибки."""

    CRITICAL = "critical"  # Не восстанавливается, логирует критичное
    WARNING = "warning"  # Может быть восстановлено, логирует warning
    INFO = "info"  # Информационная, логирует info


class ErrorRetryability(str, Enum):
    """Требуемость повтора при ошибке."""

    MUST_RETRY = "must_retry"  # Всегда повторять
    SHOULD_RETRY = "should_retry"  # Повторять если возможно
    NO_RETRY = "no_retry"  # Не повторять


# ============================================================================
# Классификатор ошибок
# ============================================================================


class ErrorClassifier:
    """Классифицирует ошибки по типу и определяет стратегию обработки."""

    # Маппинг типов исключений на свойства обработки
    ERROR_MAP = {
        NetworkError: {
            "severity": ErrorSeverity.WARNING,
            "retryability": ErrorRetryability.SHOULD_RETRY,
            "base_delay": 2.0,
            "max_retries": 5,
        },
        RateLimitError: {
            "severity": ErrorSeverity.WARNING,
            "retryability": ErrorRetryability.MUST_RETRY,
            "base_delay": 10.0,  # Больше задержка
            "max_retries": 3,
        },
        TimeoutError: {
            "severity": ErrorSeverity.WARNING,
            "retryability": ErrorRetryability.SHOULD_RETRY,
            "base_delay": 3.0,
            "max_retries": 4,
        },
        SourceUnavailableError: {
            "severity": ErrorSeverity.WARNING,
            "retryability": ErrorRetryability.MUST_RETRY,
            "base_delay": 5.0,
            "max_retries": 3,
        },
        ParsingError: {
            "severity": ErrorSeverity.WARNING,
            "retryability": ErrorRetryability.NO_RETRY,
            "base_delay": 0,
            "max_retries": 0,
        },
        ValidationError: {
            "severity": ErrorSeverity.WARNING,
            "retryability": ErrorRetryability.NO_RETRY,
            "base_delay": 0,
            "max_retries": 0,
        },
        AuthenticationError: {
            "severity": ErrorSeverity.CRITICAL,
            "retryability": ErrorRetryability.NO_RETRY,
            "base_delay": 0,
            "max_retries": 0,
        },
    }

    @classmethod
    def classify(cls, exception: Exception) -> dict:
        """
        Классифицирует исключение и возвращает стратегию обработки.

        Args:
            exception: Исключение для классификации

        Returns:
            Словарь с параметрами обработки
        """
        # Ищем точное совпадение типа
        for exc_type, properties in cls.ERROR_MAP.items():
            if isinstance(exception, exc_type):
                return {
                    "type": exc_type.__name__,
                    **properties,
                    "exception": exception,
                }

        # По умолчанию - как критичная ошибка
        return {
            "type": exception.__class__.__name__,
            "severity": ErrorSeverity.CRITICAL,
            "retryability": ErrorRetryability.NO_RETRY,
            "base_delay": 0,
            "max_retries": 0,
            "exception": exception,
        }

    @classmethod
    def should_retry(cls, exception: Exception) -> bool:
        """Проверяет нужно ли повторять при данной ошибке."""
        classification = cls.classify(exception)
        return classification["retryability"] != ErrorRetryability.NO_RETRY


# ============================================================================
# Обработчик ошибок парсеров
# ============================================================================


class ParserErrorHandler:
    """Обработчик ошибок парсеров с поддержкой различных стратегий."""

    @staticmethod
    def log_error(exception: Exception, context: str = "") -> None:
        """
        Логирует ошибку с учетом её типа и серьезности.

        Args:
            exception: Исключение
            context: Контекст ошибки (например, имя функции)
        """
        classification = ErrorClassifier.classify(exception)
        severity = classification["severity"]
        exc_type = classification["type"]

        message = f"[{exc_type}] {str(exception)}"
        if context:
            message = f"{context}: {message}"

        if severity == ErrorSeverity.CRITICAL:
            logger.critical(message, exc_info=True)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(message)
        else:
            logger.info(message)

    @staticmethod
    def convert_to_parser_exception(exception: Exception) -> ParserException:
        """
        Конвертирует обычное исключение в парсер-исключение.

        Args:
            exception: Исходное исключение

        Returns:
            ParserException или его подтип
        """
        exc_message = str(exception)

        # HTTP ошибки
        if hasattr(exception, "status_code"):
            status_code = exception.status_code

            if status_code == 429:
                return RateLimitError(
                    f"Rate limit exceeded: {exc_message}",
                    original_exception=exception,
                )
            elif status_code in (503, 502, 504):
                return SourceUnavailableError(
                    f"Source unavailable (HTTP {status_code}): {exc_message}",
                    original_exception=exception,
                )
            elif status_code in (403, 401):
                return AuthenticationError(
                    f"Authentication failed (HTTP {status_code}): {exc_message}",
                    original_exception=exception,
                )
            elif status_code == 404:
                return SourceUnavailableError(
                    f"Source not found (HTTP {status_code}): {exc_message}",
                    original_exception=exception,
                )
            else:
                return NetworkError(
                    f"HTTP error: {exc_message}",
                    original_exception=exception,
                )

        # Network ошибки
        if "timeout" in exc_message.lower():
            return TimeoutError(
                f"Connection timeout: {exc_message}",
                original_exception=exception,
            )
        elif "connection" in exc_message.lower() or "network" in exc_message.lower():
            return NetworkError(
                f"Network error: {exc_message}",
                original_exception=exception,
            )

        # По умолчанию - парсинг ошибка
        return ParsingError(exc_message, original_exception=exception)


# ============================================================================
# Декоратор для парсеров с умной обработкой ошибок
# ============================================================================


def handle_parser_errors(func: Callable) -> Callable:
    """
    Декоратор для обработки ошибок парсеров.

    Логирует ошибку с учетом её типа и преобразует её в подходящее исключение.
    """

    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except ParserException:
            # Уже парсер исключение - пробросим дальше
            raise
        except Exception as e:
            # Преобразуем в парсер исключение
            parser_exception = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_exception, context=func.__name__)
            raise parser_exception

    return wrapper
