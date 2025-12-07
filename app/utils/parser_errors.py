"""Улучшенная обработка ошибок парсеров и унификация логирования."""

import logging
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type

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


class RateLimitError(NetworkError):
    """Ошибка превышения rate limit - требует задержки."""


class TimeoutError(NetworkError):
    """Ошибка timeout - требует повтора с увеличенной задержкой."""


class ParsingError(ParserException):
    """Ошибка парсинга - обычно постоянная, не требует повтора."""


class ValidationError(ParserException):
    """Ошибка валидации данных - постоянная, не требует повтора."""


class AuthenticationError(ParserException):
    """Ошибка аутентификации - требует исправления конфигурации."""


class SourceUnavailableError(NetworkError):
    """Источник недоступен (503, 404) - требует повтора позже."""


class DataIntegrityError(ParserException):
    """Ошибка целостности данных - данные повреждены или некорректны."""


class ConfigurationError(ParserException):
    """Ошибка конфигурации - неверные параметры настройки."""


class QuotaExceededError(RateLimitError):
    """Превышена квота использования API - требуется ожидание или повышение лимита."""


# ============================================================================
# Классификация ошибок
# ============================================================================


class ErrorSeverity(str, Enum):
    """Уровень серьезности ошибки."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ErrorRetryability(str, Enum):
    """Требуемость повтора при ошибке."""

    MUST_RETRY = "must_retry"
    SHOULD_RETRY = "should_retry"
    MAYBE_RETRY = "maybe_retry"
    NO_RETRY = "no_retry"


# ============================================================================
# Классификатор ошибок
# ============================================================================


class ErrorClassifier:
    """Классифицирует ошибки по типу и определяет стратегию обработки."""

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
            "base_delay": 10.0,
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
        DataIntegrityError: {
            "severity": ErrorSeverity.ERROR,
            "retryability": ErrorRetryability.MAYBE_RETRY,
            "base_delay": 1.0,
            "max_retries": 2,
        },
        ConfigurationError: {
            "severity": ErrorSeverity.CRITICAL,
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
        QuotaExceededError: {
            "severity": ErrorSeverity.WARNING,
            "retryability": ErrorRetryability.MUST_RETRY,
            "base_delay": 30.0,
            "max_retries": 2,
        },
    }

    @classmethod
    def classify(cls, exception: Exception) -> Dict[str, Any]:
        """Классифицирует исключение и возвращает стратегию обработки."""
        if isinstance(exception, tuple(cls.ERROR_MAP.keys())):
            for error_class, properties in cls.ERROR_MAP.items():
                if type(exception) is error_class:
                    return {
                        "type": error_class.__name__,
                        **properties,
                        "exception": exception,
                    }

        specificity_order = [
            RateLimitError,
            TimeoutError,
            SourceUnavailableError,
            AuthenticationError,
            NetworkError,
            ParsingError,
            ValidationError,
        ]

        for exc_type in specificity_order:
            if isinstance(exception, exc_type) and exc_type in cls.ERROR_MAP:
                properties = cls.ERROR_MAP[exc_type]
                return {
                    "type": exc_type.__name__,
                    **properties,
                    "exception": exception,
                }

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
        """Возвращает True если ошибку можно или нужно повторить."""
        classification = cls.classify(exception)
        retryability = classification.get("retryability")
        return retryability != ErrorRetryability.NO_RETRY


# ============================================================================
# Обработчик ошибок парсеров
# ============================================================================


class ParserErrorHandler:
    """Обработчик ошибок парсеров с поддержкой различных стратегий."""

    @staticmethod
    def log_error(exception: Exception, context: str = "") -> None:
        """Логирует ошибку с учетом её типа и серьезности."""
        classification = ErrorClassifier.classify(exception)
        severity = classification["severity"]
        exc_type = classification["type"]

        message = f"[{exc_type}] {exception}"
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
        """Конвертирует обычное исключение в парсер-исключение."""
        exc_message = str(exception)

        if hasattr(exception, "status_code"):
            status_code = exception.status_code

            if status_code == 429:
                if "quota" in exc_message.lower() or "limit exceeded" in exc_message.lower():
                    return QuotaExceededError(
                        f"API quota exceeded: {exc_message}",
                        original_exception=exception,
                    )
                return RateLimitError(
                    f"Rate limit exceeded: {exc_message}",
                    original_exception=exception,
                )
            if status_code in (503, 502, 504):
                return SourceUnavailableError(
                    f"Source unavailable (HTTP {status_code}): {exc_message}",
                    original_exception=exception,
                )
            if status_code in (403, 401):
                return AuthenticationError(
                    f"Authentication failed (HTTP {status_code}): {exc_message}",
                    original_exception=exception,
                )
            if status_code == 404:
                return SourceUnavailableError(
                    f"Source not found (HTTP {status_code}): {exc_message}",
                    original_exception=exception,
                )
            if status_code == 400:
                return ValidationError(
                    f"Bad request/data validation error (HTTP {status_code}): {exc_message}",
                    original_exception=exception,
                )
            if status_code == 500:
                return DataIntegrityError(
                    f"Server internal error - possible data corruption (HTTP {status_code}): {exc_message}",
                    original_exception=exception,
                )
            return NetworkError(
                f"HTTP error: {exc_message}",
                original_exception=exception,
            )

        lower_msg = exc_message.lower()

        if "timeout" in lower_msg:
            return TimeoutError(
                f"Connection timeout: {exc_message}",
                original_exception=exception,
            )
        if "connection" in lower_msg or "network" in lower_msg:
            return NetworkError(
                f"Network error: {exc_message}",
                original_exception=exception,
            )
        if "certificate" in lower_msg or "ssl" in lower_msg:
            return NetworkError(
                f"SSL/TLS certificate error: {exc_message}",
                original_exception=exception,
            )
        if "quota" in lower_msg or "limit exceeded" in lower_msg:
            return QuotaExceededError(
                f"API quota exceeded: {exc_message}",
                original_exception=exception,
            )

        if "json" in lower_msg or "decode" in lower_msg:
            return DataIntegrityError(
                f"Data integrity error - malformed response: {exc_message}",
                original_exception=exception,
            )
        if "validation" in lower_msg or "invalid" in lower_msg:
            return ValidationError(
                f"Validation error: {exc_message}",
                original_exception=exception,
            )

        return ParsingError(exc_message, original_exception=exception)


# ============================================================================
# Декоратор для парсеров с умной обработкой ошибок
# ============================================================================


def handle_parser_errors(func: Callable) -> Callable:
    """Декоратор, приводящий ошибки парсеров к унифицированному виду."""

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except ParserException as exc:
            ParserErrorHandler.log_error(exc, context=func.__name__)
            raise
        except Exception as exc:  # noqa: BLE001 - нужно поймать все ошибки парсера
            parser_exception = ParserErrorHandler.convert_to_parser_exception(exc)
            ParserErrorHandler.log_error(parser_exception, context=func.__name__)
            raise parser_exception

    return wrapper


# ============================================================================
# Дополнительные утилиты для работы с ошибками
# ============================================================================


class ErrorUtils:
    """Утилиты для извлечения и отображения контекста ошибок."""

    @staticmethod
    def get_error_context(exception: Exception) -> Dict[str, Any]:
        """Собирает контекст ошибки (тип + вложенная ошибка)."""
        context = {
            "error_type": type(exception).__name__,
            "error_message": str(exception),
        }

        if hasattr(exception, "original_exception") and exception.original_exception:
            orig_exc = exception.original_exception
            context["original_error_type"] = type(orig_exc).__name__
            context["original_error_message"] = str(orig_exc)

        return context

    @staticmethod
    def format_error_chain(exception: Exception) -> str:
        """Возвращает цепочку вложенных ошибок в удобочитаемом виде."""
        chain = []
        current = exception

        while current:
            chain.append(f"{type(current).__name__}: {current}")
            if hasattr(current, "original_exception") and current.original_exception:
                current = current.original_exception
            else:
                break

        return " -> ".join(chain)


__all__ = [
    "ParserException",
    "NetworkError",
    "RateLimitError",
    "TimeoutError",
    "ParsingError",
    "ValidationError",
    "AuthenticationError",
    "SourceUnavailableError",
    "DataIntegrityError",
    "ConfigurationError",
    "QuotaExceededError",
    "ErrorSeverity",
    "ErrorRetryability",
    "ErrorClassifier",
    "ParserErrorHandler",
    "handle_parser_errors",
    "ErrorUtils",
]
