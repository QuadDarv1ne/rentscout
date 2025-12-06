"""Tests for parser error handling system."""

import logging

import pytest

from app.utils.parser_errors import (
    AuthenticationError,
    ErrorClassifier,
    ErrorRetryability,
    ErrorSeverity,
    NetworkError,
    ParsingError,
    ParserErrorHandler,
    RateLimitError,
    SourceUnavailableError,
    TimeoutError,
    ValidationError,
)


# ============================================================================
# Tests для пользовательских исключений
# ============================================================================


class TestParserExceptions:
    """Тесты для пользовательских исключений парсеров."""

    def test_network_error_creation(self):
        """Тест создания NetworkError."""
        original = ValueError("Connection refused")
        error = NetworkError("Network failed", original_exception=original)

        assert str(error) == "Network failed"
        assert error.original_exception is original

    def test_rate_limit_error_is_network_error(self):
        """Тест что RateLimitError является NetworkError."""
        error = RateLimitError("Too many requests")
        assert isinstance(error, NetworkError)

    def test_timeout_error_creation(self):
        """Тест создания TimeoutError."""
        error = TimeoutError("Request timeout after 30s")
        assert "timeout" in str(error).lower()

    def test_parsing_error_creation(self):
        """Тест создания ParsingError."""
        error = ParsingError("Invalid HTML structure")
        assert isinstance(error, Exception)

    def test_authentication_error_creation(self):
        """Тест создания AuthenticationError."""
        error = AuthenticationError("Invalid credentials")
        assert "credentials" in str(error).lower()


# ============================================================================
# Tests для ErrorClassifier
# ============================================================================


class TestErrorClassifier:
    """Тесты для классификатора ошибок."""

    def test_classify_network_error(self):
        """Тест классификации NetworkError."""
        error = NetworkError("Connection failed")
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "NetworkError"
        assert classification["severity"] == ErrorSeverity.WARNING
        assert classification["retryability"] == ErrorRetryability.SHOULD_RETRY
        assert classification["base_delay"] == 2.0
        assert classification["max_retries"] == 5

    def test_classify_rate_limit_error(self):
        """Тест классификации RateLimitError."""
        error = RateLimitError("429 Too Many Requests")
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "RateLimitError"
        assert classification["severity"] == ErrorSeverity.WARNING
        assert classification["retryability"] == ErrorRetryability.MUST_RETRY
        assert classification["base_delay"] == 10.0
        assert classification["max_retries"] == 3

    def test_classify_timeout_error(self):
        """Тест классификации TimeoutError."""
        error = TimeoutError("Connection timeout")
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "TimeoutError"
        assert classification["retryability"] == ErrorRetryability.SHOULD_RETRY
        assert classification["base_delay"] == 3.0

    def test_classify_source_unavailable(self):
        """Тест классификации SourceUnavailableError."""
        error = SourceUnavailableError("HTTP 503")
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "SourceUnavailableError"
        assert classification["retryability"] == ErrorRetryability.MUST_RETRY
        assert classification["base_delay"] == 5.0

    def test_classify_parsing_error(self):
        """Тест классификации ParsingError."""
        error = ParsingError("Invalid HTML")
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "ParsingError"
        assert classification["retryability"] == ErrorRetryability.NO_RETRY
        assert classification["max_retries"] == 0

    def test_classify_validation_error(self):
        """Тест классификации ValidationError."""
        error = ValidationError("Invalid field")
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "ValidationError"
        assert classification["retryability"] == ErrorRetryability.NO_RETRY

    def test_classify_authentication_error(self):
        """Тест классификации AuthenticationError."""
        error = AuthenticationError("Invalid token")
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "AuthenticationError"
        assert classification["severity"] == ErrorSeverity.CRITICAL
        assert classification["retryability"] == ErrorRetryability.NO_RETRY

    def test_classify_unknown_exception(self):
        """Тест классификации неизвестного исключения."""
        error = ValueError("Some value error")
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "ValueError"
        assert classification["severity"] == ErrorSeverity.CRITICAL
        assert classification["retryability"] == ErrorRetryability.NO_RETRY

    def test_should_retry_network_error(self):
        """Тест should_retry для NetworkError."""
        error = NetworkError("Connection failed")
        assert ErrorClassifier.should_retry(error) is True

    def test_should_retry_rate_limit_error(self):
        """Тест should_retry для RateLimitError."""
        error = RateLimitError("Too many requests")
        assert ErrorClassifier.should_retry(error) is True

    def test_should_not_retry_parsing_error(self):
        """Тест should_retry для ParsingError."""
        error = ParsingError("Invalid HTML")
        assert ErrorClassifier.should_retry(error) is False

    def test_should_not_retry_authentication_error(self):
        """Тест should_retry для AuthenticationError."""
        error = AuthenticationError("Invalid credentials")
        assert ErrorClassifier.should_retry(error) is False


# ============================================================================
# Tests для ParserErrorHandler
# ============================================================================


class TestParserErrorHandler:
    """Тесты для обработчика ошибок парсеров."""

    def test_convert_timeout_error(self):
        """Тест конвертации timeout ошибки."""
        original_error = Exception("timeout: 30 seconds")
        converted = ParserErrorHandler.convert_to_parser_exception(original_error)

        assert isinstance(converted, TimeoutError)
        assert "timeout" in str(converted).lower()
        assert converted.original_exception is original_error

    def test_convert_connection_error(self):
        """Тест конвертации connection ошибки."""
        original_error = Exception("Connection refused to server")
        converted = ParserErrorHandler.convert_to_parser_exception(original_error)

        assert isinstance(converted, NetworkError)
        assert converted.original_exception is original_error

    def test_convert_http_429_error(self):
        """Тест конвертации HTTP 429 ошибки."""

        class HttpError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        original_error = HttpError("Too Many Requests", 429)
        converted = ParserErrorHandler.convert_to_parser_exception(original_error)

        assert isinstance(converted, RateLimitError)

    def test_convert_http_503_error(self):
        """Тест конвертации HTTP 503 ошибки."""

        class HttpError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        original_error = HttpError("Service Unavailable", 503)
        converted = ParserErrorHandler.convert_to_parser_exception(original_error)

        assert isinstance(converted, SourceUnavailableError)

    def test_convert_http_401_error(self):
        """Тест конвертации HTTP 401 ошибки."""

        class HttpError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        original_error = HttpError("Unauthorized", 401)
        converted = ParserErrorHandler.convert_to_parser_exception(original_error)

        assert isinstance(converted, AuthenticationError)

    def test_convert_http_404_error(self):
        """Тест конвертации HTTP 404 ошибки."""

        class HttpError(Exception):
            def __init__(self, message, status_code):
                super().__init__(message)
                self.status_code = status_code

        original_error = HttpError("Not Found", 404)
        converted = ParserErrorHandler.convert_to_parser_exception(original_error)

        assert isinstance(converted, SourceUnavailableError)

    def test_log_error_critical(self, caplog, monkeypatch):
        """Тест логирования critical ошибки."""
        # Используем монкипатч для перехвата вывода логера
        from unittest.mock import MagicMock

        mock_logger = MagicMock()
        monkeypatch.setattr("app.utils.parser_errors.logger", mock_logger)

        error = AuthenticationError("Invalid token")
        ParserErrorHandler.log_error(error, context="test_function")

        # Проверяем что critical был вызван
        assert mock_logger.critical.called
        args = mock_logger.critical.call_args[0][0]
        assert "AuthenticationError" in args
        assert "test_function" in args

    def test_log_error_warning(self, caplog, monkeypatch):
        """Тест логирования warning ошибки."""
        from unittest.mock import MagicMock

        mock_logger = MagicMock()
        monkeypatch.setattr("app.utils.parser_errors.logger", mock_logger)

        error = NetworkError("Connection failed")
        ParserErrorHandler.log_error(error, context="test_function")

        # Проверяем что warning был вызван
        assert mock_logger.warning.called
        args = mock_logger.warning.call_args[0][0]
        assert "NetworkError" in args

    def test_convert_preserves_original_message(self):
        """Тест что конвертация сохраняет оригинальное сообщение."""
        original_message = "Specific error details"
        original_error = Exception(original_message)
        converted = ParserErrorHandler.convert_to_parser_exception(original_error)

        assert original_message in str(converted)


# ============================================================================
# Integration Tests
# ============================================================================


class TestErrorHandlingIntegration:
    """Интеграционные тесты для системы обработки ошибок."""

    def test_error_classification_chain(self):
        """Тест цепочки классификации ошибок."""
        # Создаем сложную ошибку
        original_error = Exception("timeout: 30 seconds")

        # Конвертируем в парсер ошибку
        parser_error = ParserErrorHandler.convert_to_parser_exception(original_error)
        assert isinstance(parser_error, TimeoutError)

        # Классифицируем
        classification = ErrorClassifier.classify(parser_error)
        assert classification["retryability"] == ErrorRetryability.SHOULD_RETRY

    def test_retry_strategy_for_rate_limit(self):
        """Тест стратегии повтора для rate limit."""
        error = RateLimitError("429")
        classification = ErrorClassifier.classify(error)

        # Rate limit требует повтора с большей задержкой
        assert classification["retryability"] == ErrorRetryability.MUST_RETRY
        assert classification["base_delay"] == 10.0
        assert classification["max_retries"] == 3

    def test_retry_strategy_for_parsing_error(self):
        """Тест стратегии повтора для парсинга ошибки."""
        error = ParsingError("Invalid HTML")
        classification = ErrorClassifier.classify(error)

        # Парсинг ошибка не требует повтора
        assert classification["retryability"] == ErrorRetryability.NO_RETRY
        assert classification["base_delay"] == 0
        assert classification["max_retries"] == 0

    def test_all_error_types_classified(self):
        """Тест что все типы ошибок классифицированы."""
        error_types = [
            NetworkError("Network error"),
            RateLimitError("Rate limit"),
            TimeoutError("Timeout"),
            SourceUnavailableError("503"),
            ParsingError("Parsing failed"),
            ValidationError("Validation failed"),
            AuthenticationError("Auth failed"),
        ]

        for error in error_types:
            classification = ErrorClassifier.classify(error)
            assert "type" in classification
            assert "severity" in classification
            assert "retryability" in classification
            assert "base_delay" in classification
            assert "max_retries" in classification


# ============================================================================
# Edge Cases
# ============================================================================


class TestErrorHandlingEdgeCases:
    """Тесты edge cases в обработке ошибок."""

    def test_nested_original_exceptions(self):
        """Тест обработки вложенных исключений."""
        inner_error = ValueError("Inner error")
        outer_error = NetworkError("Outer error", original_exception=inner_error)

        assert outer_error.original_exception is inner_error

    def test_empty_error_message(self):
        """Тест обработки пустого сообщения об ошибке."""
        error = NetworkError("")
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "NetworkError"

    def test_very_long_error_message(self):
        """Тест обработки очень длинного сообщения об ошибке."""
        long_message = "Error: " + "x" * 1000
        error = ParsingError(long_message)
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "ParsingError"

    def test_error_with_special_characters(self):
        """Тест обработки ошибки со специальными символами."""
        message = "Error: 错误 🚨 [CRITICAL] failure #123"
        error = NetworkError(message)
        classification = ErrorClassifier.classify(error)

        assert classification["type"] == "NetworkError"
        assert message in str(error)

    def test_classification_consistency(self):
        """Тест что классификация консистентна."""
        error = RateLimitError("Rate limit")

        # Классифицируем несколько раз
        classifications = [ErrorClassifier.classify(error) for _ in range(5)]

        # Все должны быть идентичны
        for i in range(1, len(classifications)):
            assert classifications[i] == classifications[0]
