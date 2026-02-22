"""
Тесты для глобальных обработчиков исключений (unit-тесты).
"""

import pytest

from app.middleware.exception_handler import ErrorResponse


class TestErrorResponse:
    """Тесты шаблонов ответов."""

    def test_validation_error_template(self):
        """Тест шаблона ошибки валидации."""
        response = ErrorResponse.validation_error(
            errors=[{"loc": ["body", "name"], "msg": "field required"}]
        )
        assert response["error"] == "validation_error"
        assert "details" in response
        assert len(response["details"]) > 0

    def test_internal_error_template(self):
        """Тест шаблона внутренней ошибки."""
        response = ErrorResponse.internal_error(
            message="Test error",
            request_id="test-123"
        )
        assert response["error"] == "internal_error"
        assert response["message"] == "Test error"
        assert response["request_id"] == "test-123"

    def test_internal_error_template_no_request_id(self):
        """Тест шаблона внутренней ошибки без request_id."""
        response = ErrorResponse.internal_error(message="Test error")
        assert response["error"] == "internal_error"
        assert response["message"] == "Test error"
        assert "request_id" not in response

    def test_parser_error_template(self):
        """Тест шаблона ошибки парсера."""
        response = ErrorResponse.parser_error(
            error_type="NetworkError",
            message="Connection failed",
            retryable=True,
            retry_after=5.0
        )
        assert response["error"] == "parser_error"
        assert response["error_type"] == "NetworkError"
        assert response["retryable"] is True
        assert response["retry_after"] == 5.0

    def test_parser_error_template_not_retryable(self):
        """Тест шаблона ошибки парсера без повтора."""
        response = ErrorResponse.parser_error(
            error_type="ValidationError",
            message="Invalid data",
            retryable=False
        )
        assert response["error"] == "parser_error"
        assert response["error_type"] == "ValidationError"
        assert response["retryable"] is False
        assert "retry_after" not in response

    def test_not_found_template(self):
        """Тест шаблона ошибки 404."""
        response = ErrorResponse.not_found(
            resource="Property",
            resource_id=123
        )
        assert response["error"] == "not_found"
        assert "123" in response["message"]
        assert "Property" in response["message"]

    def test_forbidden_template(self):
        """Тест шаблона ошибки 403."""
        response = ErrorResponse.forbidden(message="Access denied")
        assert response["error"] == "forbidden"
        assert response["message"] == "Access denied"

    def test_rate_limit_template(self):
        """Тест шаблона rate limit."""
        response = ErrorResponse.rate_limit(
            message="Too many requests",
            retry_after=60.0
        )
        assert response["error"] == "rate_limit"
        assert response["message"] == "Too many requests"
        assert response["retry_after"] == 60.0

    def test_rate_limit_template_no_retry_after(self):
        """Тест шаблона rate limit без retry_after."""
        response = ErrorResponse.rate_limit(message="Too many requests")
        assert response["error"] == "rate_limit"
        assert "retry_after" not in response

    def test_database_error_template(self):
        """Тест шаблона ошибки БД."""
        response = ErrorResponse.database_error(
            message="Connection failed",
            details="Timeout after 30s"
        )
        assert response["error"] == "database_error"
        assert response["message"] == "Connection failed"
        assert response["details"] == "Timeout after 30s"

    def test_database_error_template_no_details(self):
        """Тест шаблона ошибки БД без деталей."""
        response = ErrorResponse.database_error(message="Connection failed")
        assert response["error"] == "database_error"
        assert "details" not in response

    def test_cache_error_template(self):
        """Тест шаблона ошибки кеша."""
        response = ErrorResponse.cache_error(
            message="Redis unavailable",
            fallback="Using database"
        )
        assert response["error"] == "cache_error"
        assert response["message"] == "Redis unavailable"
        assert response["fallback"] == "Using database"

    def test_get_exception_summary(self):
        """Тест сводки обработчиков."""
        from app.middleware.exception_handler import get_exception_summary
        
        summary = get_exception_summary()
        assert "RequestValidationError" in summary
        assert "ParserException" in summary
        assert "SQLAlchemyError" in summary
        assert "Exception" in summary


class TestParserErrorHandling:
    """Тесты обработки ошибок парсеров."""

    def test_error_classifier_network_error(self):
        """Тест классификации ошибки сети."""
        from app.utils.parser_errors import ErrorClassifier, NetworkError
        
        exc = NetworkError("Connection failed")
        classification = ErrorClassifier.classify(exc)
        
        assert classification["type"] == "NetworkError"
        assert classification["retryability"].value == "should_retry"

    def test_error_classifier_rate_limit(self):
        """Тест классификации ошибки rate limit."""
        from app.utils.parser_errors import ErrorClassifier, RateLimitError
        
        exc = RateLimitError("Rate limit exceeded")
        classification = ErrorClassifier.classify(exc)
        
        assert classification["type"] == "RateLimitError"
        assert classification["retryability"].value == "must_retry"

    def test_error_classifier_validation(self):
        """Тест классификации ошибки валидации."""
        from app.utils.parser_errors import ErrorClassifier, ValidationError
        
        exc = ValidationError("Invalid data")
        classification = ErrorClassifier.classify(exc)
        
        assert classification["type"] == "ValidationError"
        assert classification["retryability"].value == "no_retry"

    def test_should_retry(self):
        """Тест определения возможности повтора."""
        from app.utils.parser_errors import ErrorClassifier, NetworkError, ValidationError
        
        network_exc = NetworkError("Connection failed")
        validation_exc = ValidationError("Invalid data")
        
        assert ErrorClassifier.should_retry(network_exc) is True
        assert ErrorClassifier.should_retry(validation_exc) is False
