import time
from fastapi import APIRouter, Depends, Query
from typing import Dict, Optional, Any

from app.core.config import settings
from app.services.advanced_cache import advanced_cache_manager
from app.utils.ip_ratelimiter import ip_rate_limiter
from app.utils.logger import logger
from app.utils.metrics import metrics_collector, ACTIVE_REQUESTS
from app.utils.parser_errors import ErrorClassifier, ErrorSeverity, ErrorRetryability

router = APIRouter()


@router.get("/health", tags=["health"])
async def health_check() -> Dict[str, str]:
    """Проверка состояния приложения."""
    return {"status": "healthy"}


@router.get("/health/detailed", tags=["health"])
async def detailed_health_check() -> Dict[str, object]:
    """Подробная проверка состояния приложения."""
    # Здесь можно добавить проверки подключений к базам данных, кэша и т.д.
    health_status = {"status": "healthy", "timestamp": time.time(), "app_name": settings.APP_NAME, "version": "1.0.0"}

    logger.info("Detailed health check performed")
    return health_status


@router.get("/stats", tags=["health"])
async def get_stats() -> Dict[str, object]:
    """Получение статистики приложения."""
    # Собираем статистику кеша
    cache_stats = await advanced_cache_manager.get_stats()
    active_requests = ACTIVE_REQUESTS._value.get()  # Gauge current value
    
    stats = {
        "uptime_seconds": metrics_collector.get_uptime(),
        "app_name": settings.APP_NAME,
        "version": "1.0.0",
        "cache": cache_stats,
        "active_requests": active_requests,
    }

    logger.info("Stats requested")
    return stats


@router.get("/cache/stats", tags=["health"])
async def get_cache_stats() -> Dict[str, object]:
    """Получение детальной статистики кеша."""
    cache_stats = await advanced_cache_manager.get_stats()
    logger.info(f"Cache stats: {cache_stats}")
    return cache_stats


@router.get("/ratelimit/stats", tags=["health"])
async def get_ratelimit_stats() -> Dict[str, object]:
    """Получение статистики rate limiting."""
    stats = ip_rate_limiter.get_stats()
    logger.info(f"Rate limit stats: {stats}")
    return stats


@router.get("/errors/diagnostic", tags=["health"])
async def diagnose_error(
    error_type: Optional[str] = Query(None, description="Тип ошибки для диагностики"),
) -> Dict[str, Any]:
    """
    Диагностика ошибок парсера и их рекомендации.
    
    Args:
        error_type: Тип ошибки (например 'TimeoutError', 'NetworkError')
        
    Returns:
        Информация о типах ошибок и рекомендации
    """
    error_info = {
        "supported_error_types": [
            "NetworkError",
            "TimeoutError",
            "RateLimitError",
            "AuthenticationError",
            "ParsingError",
            "ValidationError",
            "SourceUnavailableError",
            "DataIntegrityError",
            "ConfigurationError",
            "QuotaExceededError",
        ],
        "error_classifications": {
            "NetworkError": {
                "severity": "WARNING",
                "retryability": "RETRY_WITH_BACKOFF",
                "recommendation": "Проверьте подключение к интернету и статус целевого сервера",
                "typical_http_code": 503,
            },
            "TimeoutError": {
                "severity": "WARNING",
                "retryability": "RETRY_WITH_BACKOFF",
                "recommendation": "Увеличьте timeout или повторите попытку позже",
                "typical_http_code": 504,
            },
            "RateLimitError": {
                "severity": "WARNING",
                "retryability": "RETRY_WITH_BACKOFF",
                "recommendation": "Сервер ограничил количество запросов, подождите перед следующей попыткой",
                "typical_http_code": 429,
            },
            "AuthenticationError": {
                "severity": "CRITICAL",
                "retryability": "NO_RETRY",
                "recommendation": "Проверьте учетные данные и права доступа",
                "typical_http_code": 401,
            },
            "ParsingError": {
                "severity": "WARNING",
                "retryability": "RETRY_LIMIT",
                "recommendation": "Структура данных на сайте изменилась, требуется обновление парсера",
                "typical_http_code": 400,
            },
            "ValidationError": {
                "severity": "WARNING",
                "retryability": "NO_RETRY",
                "recommendation": "Проверьте формат входных данных",
                "typical_http_code": 422,
            },
            "SourceUnavailableError": {
                "severity": "CRITICAL",
                "retryability": "RETRY_LIMIT",
                "recommendation": "Сервис источника недоступен или заблокирован",
                "typical_http_code": 503,
            },
        }
    }
    
    # Если конкретный тип ошибки не указан, возвращаем полный список
    if error_type:
        if error_type in error_info["error_classifications"]:
            return {
                "error_type": error_type,
                "details": error_info["error_classifications"][error_type],
            }
        else:
            return {
                "error": f"Unknown error type: {error_type}",
                "supported_types": error_info["supported_error_types"],
            }
    
    logger.info("Provided error diagnostic information")
    return error_info
