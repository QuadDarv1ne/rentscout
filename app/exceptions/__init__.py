"""
Exceptions package for RentScout API.

Provides standardized exception classes for consistent error handling.
"""

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
