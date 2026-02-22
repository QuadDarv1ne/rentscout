"""
Глобальные обработчики исключений для унифицированных ответов API.

Использование:
    from app.middleware.exception_handler import setup_exception_handlers
    setup_exception_handlers(app)
"""

import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError

from app.utils.logger import logger
from app.utils.parser_errors import (
    ParserException,
    NetworkError,
    RateLimitError,
    TimeoutError,
    AuthenticationError,
    SourceUnavailableError,
    QuotaExceededError,
)


# ============================================================================
# Схемы ответов об ошибках
# ============================================================================

class ErrorResponse:
    """Шаблоны ответов об ошибках."""

    @staticmethod
    def validation_error(errors: list, message: str = "Invalid request parameters") -> dict:
        return {
            "error": "validation_error",
            "message": message,
            "details": errors,
        }

    @staticmethod
    def internal_error(
        message: str = "An unexpected error occurred",
        request_id: Optional[str] = None
    ) -> dict:
        response = {
            "error": "internal_error",
            "message": message,
        }
        if request_id:
            response["request_id"] = request_id
        return response

    @staticmethod
    def parser_error(
        error_type: str,
        message: str,
        retryable: bool = False,
        retry_after: Optional[float] = None
    ) -> dict:
        response = {
            "error": "parser_error",
            "error_type": error_type,
            "message": message,
            "retryable": retryable,
        }
        if retry_after is not None:
            response["retry_after"] = retry_after
        return response

    @staticmethod
    def not_found(resource: str, resource_id: Any) -> dict:
        return {
            "error": "not_found",
            "message": f"{resource} with id '{resource_id}' not found",
        }

    @staticmethod
    def forbidden(message: str = "Access denied") -> dict:
        return {
            "error": "forbidden",
            "message": message,
        }

    @staticmethod
    def rate_limit(
        message: str = "Rate limit exceeded",
        retry_after: Optional[float] = None
    ) -> dict:
        response = {
            "error": "rate_limit",
            "message": message,
        }
        if retry_after is not None:
            response["retry_after"] = retry_after
        return response

    @staticmethod
    def database_error(
        message: str = "Database error occurred",
        details: Optional[str] = None
    ) -> dict:
        response = {
            "error": "database_error",
            "message": message,
        }
        if details:
            response["details"] = details
        return response

    @staticmethod
    def cache_error(
        message: str = "Cache error occurred",
        fallback: str = "Proceeding without cache"
    ) -> dict:
        return {
            "error": "cache_error",
            "message": message,
            "fallback": fallback,
        }


# ============================================================================
# Обработчики исключений
# ============================================================================

async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """Обработчик ошибок валидации запроса."""
    logger.warning(
        f"Validation error on {request.method} {request.url.path}: {exc.errors()}"
    )

    headers = {}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse.validation_error(exc.errors()),
        headers=headers,
    )


async def pydantic_validation_exception_handler(
    request: Request,
    exc: ValidationError
) -> JSONResponse:
    """Обработчик ошибок валидации Pydantic."""
    logger.warning(
        f"Pydantic validation error on {request.method} {request.url.path}: {exc.errors()}"
    )

    headers = {}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse.validation_error(exc.errors()),
        headers=headers,
    )


async def parser_exception_handler(
    request: Request,
    exc: ParserException
) -> JSONResponse:
    """Обработчик ошибок парсеров."""
    from app.utils.parser_errors import ErrorClassifier, ErrorRetryability

    classification = ErrorClassifier.classify(exc)
    retryability = classification.get("retryability", ErrorRetryability.NO_RETRY)
    base_delay = classification.get("base_delay", 0)

    is_retryable = retryability in (
        ErrorRetryability.MUST_RETRY,
        ErrorRetryability.SHOULD_RETRY,
        ErrorRetryability.MAYBE_RETRY,
    )

    # Определяем HTTP статус
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    if isinstance(exc, (RateLimitError, QuotaExceededError)):
        status_code = status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(exc, (AuthenticationError,)):
        status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, (SourceUnavailableError,)):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, (TimeoutError,)):
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
    elif isinstance(exc, (ValidationError,)):
        status_code = status.HTTP_400_BAD_REQUEST

    logger.warning(
        f"Parser error on {request.method} {request.url.path}: "
        f"{type(exc).__name__} - {exc}"
    )

    headers = {}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse.parser_error(
            error_type=type(exc).__name__,
            message=str(exc),
            retryable=is_retryable,
            retry_after=base_delay if is_retryable else None,
        ),
        headers=headers,
    )


async def sqlalchemy_exception_handler(
    request: Request,
    exc: SQLAlchemyError
) -> JSONResponse:
    """Обработчик ошибок базы данных."""
    logger.error(
        f"Database error on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )

    headers = {}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse.database_error(
            message="Database operation failed",
            details=str(exc) if getattr(request.app.state, "debug", False) else None,
        ),
        headers=headers,
    )


async def redis_exception_handler(
    request: Request,
    exc: RedisError
) -> JSONResponse:
    """Обработчик ошибок Redis."""
    logger.error(
        f"Redis error on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )

    headers = {}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ErrorResponse.cache_error(
            message="Cache service unavailable",
            fallback="Proceeding without cache",
        ),
        headers=headers,
    )


async def http_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Обработчик HTTP исключений FastAPI."""
    from fastapi import HTTPException

    if not isinstance(exc, HTTPException):
        raise exc

    logger.warning(
        f"HTTP error {exc.status_code} on {request.method} {request.url.path}: {exc.detail}"
    )

    content = {
        "error": "http_error",
        "status_code": exc.status_code,
        "message": exc.detail,
    }

    if exc.status_code == status.HTTP_404_NOT_FOUND:
        content["error"] = "not_found"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        content["error"] = "forbidden"
    elif exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        content["error"] = "rate_limit"
        if exc.headers and "Retry-After" in exc.headers:
            content["retry_after"] = float(exc.headers["Retry-After"])

    return JSONResponse(
        status_code=exc.status_code,
        content=content,
        headers=getattr(exc, "headers", None),
    )


async def global_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Глобальный обработчик всех необработанных исключений."""
    logger.error(
        f"Unhandled error on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )

    request_id = getattr(request.state, "request_id", None)

    headers = {}
    if request_id:
        headers["X-Request-ID"] = request_id

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse.internal_error(
            message="An unexpected error occurred",
            request_id=request_id,
        ),
        headers=headers,
    )


async def not_found_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Обработчик ошибок 404."""
    from starlette.exceptions import HTTPException

    if not isinstance(exc, HTTPException) or exc.status_code != 404:
        raise exc

    logger.info(f"Resource not found: {request.method} {request.url.path}")

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=ErrorResponse.not_found(
            resource="Resource",
            resource_id=request.url.path,
        ),
        headers={"X-Request-ID": getattr(request.state, "request_id", None)},
    )


# ============================================================================
# Регистрация обработчиков
# ============================================================================

def setup_exception_handlers(app: FastAPI) -> None:
    """
    Регистрирует все обработчики исключений в приложении.

    Args:
        app: Экземпляр FastAPI приложения
    """
    from fastapi import HTTPException
    from starlette.exceptions import HTTPException as StarletteHTTPException

    # Валидация
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_exception_handler)

    # Парсеры
    app.add_exception_handler(ParserException, parser_exception_handler)
    app.add_exception_handler(NetworkError, parser_exception_handler)
    app.add_exception_handler(RateLimitError, parser_exception_handler)
    app.add_exception_handler(TimeoutError, parser_exception_handler)
    app.add_exception_handler(AuthenticationError, parser_exception_handler)
    app.add_exception_handler(SourceUnavailableError, parser_exception_handler)
    app.add_exception_handler(QuotaExceededError, parser_exception_handler)

    # БД и кеш
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(RedisError, redis_exception_handler)

    # HTTP исключения (должны быть перед общим Exception handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, not_found_handler)

    # Глобальный обработчик (должен быть последним)
    app.add_exception_handler(Exception, global_exception_handler)

    logger.info("✅ Exception handlers registered")


def get_exception_summary() -> Dict[str, str]:
    """Возвращает сводку зарегистрированных обработчиков."""
    return {
        "RequestValidationError": "HTTP 422 - Ошибки валидации запроса",
        "ValidationError": "HTTP 422 - Ошибки валидации Pydantic",
        "ParserException": "HTTP 400-504 - Ошибки парсеров (зависит от типа)",
        "SQLAlchemyError": "HTTP 500 - Ошибки базы данных",
        "RedisError": "HTTP 503 - Ошибки Redis/кеша",
        "HTTPException": "HTTP N - Стандартные HTTP ошибки",
        "Exception": "HTTP 500 - Все необработанные ошибки",
    }


__all__ = [
    "ErrorResponse",
    "setup_exception_handlers",
    "get_exception_summary",
    # Обработчики
    "request_validation_exception_handler",
    "pydantic_validation_exception_handler",
    "parser_exception_handler",
    "sqlalchemy_exception_handler",
    "redis_exception_handler",
    "http_exception_handler",
    "global_exception_handler",
    "not_found_handler",
]
