"""
Enhanced HTTP exception classes with standardized error codes.

Provides specific exception classes for common API errors with:
- Standardized error codes
- Consistent error messages
- Additional context data
- Retry information
"""
from typing import Any, Dict, Optional, List
from fastapi import HTTPException, status


class APIException(HTTPException):
    """Base class for all API exceptions."""

    error_code: str = "api_error"
    default_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message: str = "An API error occurred"

    def __init__(
        self,
        message: Optional[str] = None,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.error_code = error_code or self.error_code
        self.details = details or {}
        self.message = message or self.default_message

        super().__init__(
            status_code=status_code or self.default_status,
            detail=self.message,
            headers=headers,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "error": self.error_code,
            "message": self.detail,
            "details": self.details,
        }


class ValidationException(APIException):
    """Request validation error."""

    error_code = "validation_error"
    default_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_message = "Request validation failed"

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            details={"fields": details} if details else None,
            **kwargs,
        )


class NotFoundException(APIException):
    """Resource not found error."""

    error_code = "not_found"
    default_status = status.HTTP_404_NOT_FOUND
    default_message = "Resource not found"

    def __init__(
        self,
        resource: str = "Resource",
        resource_id: Any = None,
        message: Optional[str] = None,
        **kwargs,
    ):
        msg = message or f"{resource} with id '{resource_id}' not found"
        super().__init__(
            message=msg,
            details={"resource": resource, "resource_id": resource_id},
            **kwargs,
        )


class UnauthorizedException(APIException):
    """Authentication required error."""

    error_code = "unauthorized"
    default_status = status.HTTP_401_UNAUTHORIZED
    default_message = "Authentication required"

    def __init__(
        self,
        message: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message=message, **kwargs)


class ForbiddenException(APIException):
    """Access denied error."""

    error_code = "forbidden"
    default_status = status.HTTP_403_FORBIDDEN
    default_message = "Access denied"

    def __init__(
        self,
        message: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message=message, **kwargs)


class RateLimitException(APIException):
    """Rate limit exceeded error."""

    error_code = "rate_limit_exceeded"
    default_status = status.HTTP_429_TOO_MANY_REQUESTS
    default_message = "Rate limit exceeded"

    def __init__(
        self,
        message: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        headers = kwargs.get("headers", {})
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)

        super().__init__(
            message=message,
            details={"retry_after": retry_after} if retry_after else None,
            headers=headers if headers else None,
            **kwargs,
        )


class ConflictException(APIException):
    """Resource conflict error."""

    error_code = "conflict"
    default_status = status.HTTP_409_CONFLICT
    default_message = "Resource conflict"

    def __init__(
        self,
        message: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message=message, **kwargs)


class DatabaseException(APIException):
    """Database operation error."""

    error_code = "database_error"
    default_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "Database operation failed"

    def __init__(
        self,
        message: Optional[str] = None,
        details: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            details={"database_details": details} if details else None,
            **kwargs,
        )


class CacheException(APIException):
    """Cache operation error."""

    error_code = "cache_error"
    default_status = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "Cache service unavailable"

    def __init__(
        self,
        message: Optional[str] = None,
        fallback: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            details={"fallback": fallback} if fallback else None,
            **kwargs,
        )


class ParserException(APIException):
    """Parser operation error."""

    error_code = "parser_error"
    default_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_message = "Parser operation failed"

    def __init__(
        self,
        message: Optional[str] = None,
        parser_name: Optional[str] = None,
        retryable: bool = False,
        retry_after: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            details={
                "parser_name": parser_name,
                "retryable": retryable,
                "retry_after": retry_after,
            },
            **kwargs,
        )


class TimeoutException(APIException):
    """Request timeout error."""

    error_code = "timeout"
    default_status = status.HTTP_504_GATEWAY_TIMEOUT
    default_message = "Request timed out"

    def __init__(
        self,
        message: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            details={"timeout_seconds": timeout_seconds} if timeout_seconds else None,
            **kwargs,
        )


class ServiceUnavailableException(APIException):
    """Service temporarily unavailable."""

    error_code = "service_unavailable"
    default_status = status.HTTP_503_SERVICE_UNAVAILABLE
    default_message = "Service temporarily unavailable"

    def __init__(
        self,
        message: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        headers = kwargs.get("headers", {})
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)

        super().__init__(
            message=message,
            details={"retry_after": retry_after} if retry_after else None,
            headers=headers if headers else None,
            **kwargs,
        )


class InvalidRequestException(APIException):
    """Invalid request format or content."""

    error_code = "invalid_request"
    default_status = status.HTTP_400_BAD_REQUEST
    default_message = "Invalid request"

    def __init__(
        self,
        message: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message=message, **kwargs)


class DuplicateResourceException(APIException):
    """Resource already exists."""

    error_code = "duplicate_resource"
    default_status = status.HTTP_409_CONFLICT
    default_message = "Resource already exists"

    def __init__(
        self,
        resource: str = "Resource",
        message: Optional[str] = None,
        **kwargs,
    ):
        msg = message or f"{resource} already exists"
        super().__init__(
            message=msg,
            details={"resource": resource},
            **kwargs,
        )


class QuotaExceededException(APIException):
    """Quota exceeded error."""

    error_code = "quota_exceeded"
    default_status = status.HTTP_429_TOO_MANY_REQUESTS
    default_message = "Quota exceeded"

    def __init__(
        self,
        message: Optional[str] = None,
        quota_limit: Optional[int] = None,
        quota_remaining: int = 0,
        reset_time: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            details={
                "quota_limit": quota_limit,
                "quota_remaining": quota_remaining,
                "reset_time": reset_time,
            },
            **kwargs,
        )


# ============================================================================
# Helper functions
# ============================================================================

def raise_not_found(resource: str = "Resource", resource_id: Any = None):
    """Raise NotFoundException."""
    raise NotFoundException(resource=resource, resource_id=resource_id)


def raise_unauthorized(message: str = "Authentication required"):
    """Raise UnauthorizedException."""
    raise UnauthorizedException(message=message)


def raise_forbidden(message: str = "Access denied"):
    """Raise ForbiddenException."""
    raise ForbiddenException(message=message)


def raise_rate_limit(retry_after: Optional[int] = None):
    """Raise RateLimitException."""
    raise RateLimitException(retry_after=retry_after)


def raise_validation_error(details: Optional[List[Dict[str, Any]]] = None):
    """Raise ValidationException."""
    raise ValidationException(details=details)


def raise_conflict(message: str = "Resource conflict"):
    """Raise ConflictException."""
    raise ConflictException(message=message)


def raise_duplicate(resource: str = "Resource"):
    """Raise DuplicateResourceException."""
    raise DuplicateResourceException(resource=resource)


__all__ = [
    # Exception classes
    "APIException",
    "ValidationException",
    "NotFoundException",
    "UnauthorizedException",
    "ForbiddenException",
    "RateLimitException",
    "ConflictException",
    "DatabaseException",
    "CacheException",
    "ParserException",
    "TimeoutException",
    "ServiceUnavailableException",
    "InvalidRequestException",
    "DuplicateResourceException",
    "QuotaExceededException",
    # Helper functions
    "raise_not_found",
    "raise_unauthorized",
    "raise_forbidden",
    "raise_rate_limit",
    "raise_validation_error",
    "raise_conflict",
    "raise_duplicate",
]
