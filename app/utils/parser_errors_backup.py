"""Улучшенная обработка ошибок парсеров с специфичными типами и обработками."""

import logging
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, Dict

from app.utils.logger import logger

# ============================================================================
# Пользовательские исключения парсеров
# ============================================================================


class ParserException(Exception):
    """Базовое исключение для всех ошибок парсеров."""

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        def handle_parser_errors(func: Callable) -> Callable:
            """Декоратор, приводящий ошибки парсеров к унифицированному виду."""

            @wraps(func)
            async def wrapper(*args, **kwargs) -> Any:
                try:
                    return await func(*args, **kwargs)
                except ParserException as exc:
                    # Логируем уже нормализованную ошибку, чтобы не терять контекст
                    ParserErrorHandler.log_error(exc, context=func.__name__)
                    raise
                except Exception as exc:  # noqa: BLE001 - нужно поймать все ошибки парсера
                    parser_exception = ParserErrorHandler.convert_to_parser_exception(exc)
                    ParserErrorHandler.log_error(parser_exception, context=func.__name__)
                    raise parser_exception

            return wrapper


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
            "base_delay": 30.0,  # Большая задержка
            "max_retries": 2,
        },
    }

    @classmethod
    def classify(cls, exception: Exception) -> Dict[str, Any]:
        """
        Классифицирует исключение и возвращает стратегию обработки.

        Args:
            exception: Исключение для классификации

        Returns:
            Словарь с параметрами обработки
        """
        # Сначала проверяем точное совпадение типа (в порядке специфичности)
        exc_type: Type[Exception] = type(exception)
        if isinstance(exception, tuple(cls.ERROR_MAP.keys())):
            for error_class, properties in cls.ERROR_MAP.items():
                if type(exception) is error_class:
                    return {
                        "type": error_class.__name__,
                        **properties,
                        "exception": exception,
                    }

        # Затем проверяем наследование (по порядку, специфичные типы первыми)
        # Порядок важен: проверяем подклассы ДО их родителей
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
        retryability = classification.get("retryability")
        return retryability != ErrorRetryability.NO_RETRY


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
                # Проверяем на квоту
                if "quota" in exc_message.lower() or "limit exceeded" in exc_message.lower():
                    return QuotaExceededError(
                        f"API quota exceeded: {exc_message}",
                        original_exception=exception,
                    )
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
            elif status_code == 400:
                return ValidationError(
                    f"Bad request/data validation error (HTTP {status_code}): {exc_message}",
                    original_exception=exception,
                )
            elif status_code == 500:
                return DataIntegrityError(
                    f"Server internal error - possible data corruption (HTTP {status_code}): {exc_message}",
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
        elif "certificate" in exc_message.lower() or "ssl" in exc_message.lower():
            return NetworkError(
                f"SSL/TLS certificate error: {exc_message}",
                original_exception=exception,
            )
        elif "quota" in exc_message.lower() or "limit exceeded" in exc_message.lower():
            return QuotaExceededError(
                f"API quota exceeded: {exc_message}",
                original_exception=exception,
            )

        # JSON/данные ошибки
        if "json" in exc_message.lower() or "decode" in exc_message.lower():
            return DataIntegrityError(
                f"Data integrity error - malformed response: {exc_message}",
                original_exception=exception,
            )
        elif "validation" in exc_message.lower() or "invalid" in exc_message.lower():
            return ValidationError(
                f"Validation error: {exc_message}",
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


# Дополнительные утилиты для работы с ошибками

class ErrorUtils:
    """Утилиты для работы с ошибками."""
    
    @staticmethod
    def get_error_context(exception: Exception) -> Dict[str, Any]:
        """
        Получает контекст ошибки для логирования.
        
        Args:
            exception: Исключение
            
        Returns:
            Словарь с контекстом ошибки
        """
        context = {
            "error_type": type(exception).__name__,
            "error_message": str(exception),
        }
        
        # Добавляем контекст из оригинального исключения
        if hasattr(exception, "original_exception") and exception.original_exception:
            orig_exc = exception.original_exception
            context["original_error_type"] = type(orig_exc).__name__
            context["original_error_message"] = str(orig_exc)
            
        return context
    
    @staticmethod
    def format_error_chain(exception: Exception) -> str:
        """
        Форматирует цепочку ошибок для логирования.
        
        Args:
            exception: Исключение
            
        Returns:
            Строка с цепочкой ошибок
        """
        chain = []
        current = exception
        
        while current:
            chain.append(f"{type(current).__name__}: {current}")
            if hasattr(current, "original_exception") and current.original_exception:
                current = current.original_exception
            else:
                break
                
        return " -> ".join(chain)


    return wrapper


# Дополнительные утилиты для работы с ошибками

class ErrorUtils:
    """Утилиты для работы с ошибками."""
    
    @staticmethod
    def get_error_context(exception: Exception) -> Dict[str, Any]:
        """
        Получает контекст ошибки для логирования.
        
        Args:
            exception: Исключение
            
        Returns:
            Словарь с контекстом ошибки
        """
        context = {
            "error_type": type(exception).__name__,
            "error_message": str(exception),
        }
        
        # Добавляем контекст из оригинального исключения
        if hasattr(exception, "original_exception") and exception.original_exception:
            orig_exc = exception.original_exception
            context["original_error_type"] = type(orig_exc).__name__
            context["original_error_message"] = str(orig_exc)
            
        return context
    
    @staticmethod
    def format_error_chain(exception: Exception) -> str:
        """
        Форматирует цепочку ошибок для логирования.
        
        Args:
            exception: Исключение
            
        Returns:
            Строка с цепочкой ошибок
        """
        chain = []
        current = exception
        
        while current:
            chain.append(f"{type(current).__name__}: {current}")
            if hasattr(current, "original_exception") and current.original_exception:
                current = current.original_exception
            else:
                break
                
        return " -> ".join(chain)
