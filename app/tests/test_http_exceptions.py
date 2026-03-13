"""
Tests for enhanced HTTP exceptions.
"""
import pytest
from fastapi import status

from app.exceptions.http_exceptions import (
    APIException,
    ValidationException,
    NotFoundException,
    UnauthorizedException,
    ForbiddenException,
    RateLimitException,
    ConflictException,
    DatabaseException,
    CacheException,
    ParserException,
    TimeoutException,
    ServiceUnavailableException,
    InvalidRequestException,
    DuplicateResourceException,
    QuotaExceededException,
    # Helper functions
    raise_not_found,
    raise_unauthorized,
    raise_forbidden,
    raise_rate_limit,
    raise_validation_error,
    raise_conflict,
    raise_duplicate,
)


class TestAPIException:
    """Tests for base APIException."""

    def test_default_values(self):
        """Test default exception values."""
        exc = APIException()
        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc.error_code == "api_error"
        assert exc.detail == "An API error occurred"

    def test_custom_values(self):
        """Test custom exception values."""
        exc = APIException(
            message="Custom error",
            status_code=400,
            error_code="custom_error",
            details={"key": "value"},
        )
        assert exc.status_code == 400
        assert exc.error_code == "custom_error"
        assert exc.detail == "Custom error"
        assert exc.details == {"key": "value"}

    def test_to_dict(self):
        """Test exception to dictionary conversion."""
        exc = APIException(
            message="Test error",
            error_code="test_error",
            details={"field": "value"},
        )
        result = exc.to_dict()
        assert result == {
            "error": "test_error",
            "message": "Test error",
            "details": {"field": "value"},
        }


class TestValidationException:
    """Tests for ValidationException."""

    def test_default(self):
        """Test default validation exception."""
        exc = ValidationException()
        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert exc.error_code == "validation_error"

    def test_with_details(self):
        """Test validation exception with field details."""
        details = [{"field": "email", "message": "Invalid email"}]
        exc = ValidationException(details=details)
        assert exc.details["fields"] == details


class TestNotFoundException:
    """Tests for NotFoundException."""

    def test_default(self):
        """Test default not found exception."""
        exc = NotFoundException()
        assert exc.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc.detail.lower()

    def test_with_resource(self):
        """Test not found with resource info."""
        exc = NotFoundException(resource="User", resource_id=123)
        assert "User" in exc.detail
        assert "123" in exc.detail
        assert exc.details["resource"] == "User"
        assert exc.details["resource_id"] == 123


class TestUnauthorizedException:
    """Tests for UnauthorizedException."""

    def test_default(self):
        """Test default unauthorized exception."""
        exc = UnauthorizedException()
        assert exc.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc.error_code == "unauthorized"

    def test_custom_message(self):
        """Test custom message."""
        exc = UnauthorizedException(message="Token expired")
        assert exc.detail == "Token expired"


class TestForbiddenException:
    """Tests for ForbiddenException."""

    def test_default(self):
        """Test default forbidden exception."""
        exc = ForbiddenException()
        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.error_code == "forbidden"


class TestRateLimitException:
    """Tests for RateLimitException."""

    def test_default(self):
        """Test default rate limit exception."""
        exc = RateLimitException()
        assert exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exc.error_code == "rate_limit_exceeded"

    def test_with_retry_after(self):
        """Test rate limit with retry-after header."""
        exc = RateLimitException(retry_after=60)
        assert exc.headers["Retry-After"] == "60"
        assert exc.details["retry_after"] == 60


class TestConflictException:
    """Tests for ConflictException."""

    def test_default(self):
        """Test default conflict exception."""
        exc = ConflictException()
        assert exc.status_code == status.HTTP_409_CONFLICT
        assert exc.error_code == "conflict"


class TestDatabaseException:
    """Tests for DatabaseException."""

    def test_default(self):
        """Test default database exception."""
        exc = DatabaseException()
        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc.error_code == "database_error"

    def test_with_details(self):
        """Test database exception with details."""
        exc = DatabaseException(details="Connection timeout")
        assert exc.details["database_details"] == "Connection timeout"


class TestCacheException:
    """Tests for CacheException."""

    def test_default(self):
        """Test default cache exception."""
        exc = CacheException()
        assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc.error_code == "cache_error"

    def test_with_fallback(self):
        """Test cache exception with fallback."""
        exc = CacheException(fallback="Using database")
        assert exc.details["fallback"] == "Using database"


class TestParserException:
    """Tests for ParserException."""

    def test_default(self):
        """Test default parser exception."""
        exc = ParserException()
        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc.error_code == "parser_error"

    def test_with_parser_info(self):
        """Test parser exception with parser info."""
        exc = ParserException(
            parser_name="AvitoParser",
            retryable=True,
            retry_after=30.0,
        )
        assert exc.details["parser_name"] == "AvitoParser"
        assert exc.details["retryable"] is True
        assert exc.details["retry_after"] == 30.0


class TestTimeoutException:
    """Tests for TimeoutException."""

    def test_default(self):
        """Test default timeout exception."""
        exc = TimeoutException()
        assert exc.status_code == status.HTTP_504_GATEWAY_TIMEOUT
        assert exc.error_code == "timeout"

    def test_with_timeout(self):
        """Test timeout exception with seconds."""
        exc = TimeoutException(timeout_seconds=30.0)
        assert exc.details["timeout_seconds"] == 30.0


class TestServiceUnavailableException:
    """Tests for ServiceUnavailableException."""

    def test_default(self):
        """Test default service unavailable exception."""
        exc = ServiceUnavailableException()
        assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc.error_code == "service_unavailable"

    def test_with_retry_after(self):
        """Test service unavailable with retry-after."""
        exc = ServiceUnavailableException(retry_after=120)
        assert exc.headers["Retry-After"] == "120"


class TestInvalidRequestException:
    """Tests for InvalidRequestException."""

    def test_default(self):
        """Test default invalid request exception."""
        exc = InvalidRequestException()
        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert exc.error_code == "invalid_request"


class TestDuplicateResourceException:
    """Tests for DuplicateResourceException."""

    def test_default(self):
        """Test default duplicate resource exception."""
        exc = DuplicateResourceException()
        assert exc.status_code == status.HTTP_409_CONFLICT
        assert exc.error_code == "duplicate_resource"

    def test_with_resource(self):
        """Test duplicate with resource info."""
        exc = DuplicateResourceException(resource="Email")
        assert "Email" in exc.detail
        assert exc.details["resource"] == "Email"


class TestQuotaExceededException:
    """Tests for QuotaExceededException."""

    def test_default(self):
        """Test default quota exceeded exception."""
        exc = QuotaExceededException()
        assert exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exc.error_code == "quota_exceeded"

    def test_with_quota_info(self):
        """Test quota exceeded with quota info."""
        exc = QuotaExceededException(
            quota_limit=1000,
            quota_remaining=0,
            reset_time="2026-03-11T00:00:00Z",
        )
        assert exc.details["quota_limit"] == 1000
        assert exc.details["quota_remaining"] == 0


class TestHelperFunctions:
    """Tests for helper raise functions."""

    def test_raise_not_found(self):
        """Test raise_not_found helper."""
        with pytest.raises(NotFoundException) as exc_info:
            raise_not_found("User", 123)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_raise_unauthorized(self):
        """Test raise_unauthorized helper."""
        with pytest.raises(UnauthorizedException) as exc_info:
            raise_unauthorized("Token expired")
        assert exc_info.value.detail == "Token expired"

    def test_raise_forbidden(self):
        """Test raise_forbidden helper."""
        with pytest.raises(ForbiddenException) as exc_info:
            raise_forbidden("Admin only")
        assert exc_info.value.detail == "Admin only"

    def test_raise_rate_limit(self):
        """Test raise_rate_limit helper."""
        with pytest.raises(RateLimitException) as exc_info:
            raise_rate_limit(retry_after=60)
        assert exc_info.value.headers["Retry-After"] == "60"

    def test_raise_validation_error(self):
        """Test raise_validation_error helper."""
        details = [{"field": "email", "message": "Invalid"}]
        with pytest.raises(ValidationException) as exc_info:
            raise_validation_error(details=details)
        assert exc_info.value.details["fields"] == details

    def test_raise_conflict(self):
        """Test raise_conflict helper."""
        with pytest.raises(ConflictException) as exc_info:
            raise_conflict("Already exists")
        assert exc_info.value.detail == "Already exists"

    def test_raise_duplicate(self):
        """Test raise_duplicate helper."""
        with pytest.raises(DuplicateResourceException) as exc_info:
            raise_duplicate("Email")
        assert exc_info.value.details["resource"] == "Email"
