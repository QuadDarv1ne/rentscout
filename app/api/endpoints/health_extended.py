"""
Extended health check endpoints for database and services.

Provides detailed health status for:
- PostgreSQL database (connection, latency, queries)
- Redis cache (connection, memory, keys)
- External services (parsers, ML models)
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.utils.logger import logger
from app.core.config import settings
from app.db.models.session import get_db_session

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class HealthStatus(BaseModel):
    """Базовый статус здоровья."""
    status: str = Field(..., description="Общий статус")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DatabaseHealth(BaseModel):
    """Статус базы данных."""
    status: str
    connected: bool
    latency_ms: Optional[float] = None
    connections_active: Optional[int] = None
    connections_idle: Optional[int] = None
    version: Optional[str] = None
    error: Optional[str] = None


class RedisHealth(BaseModel):
    """Статус Redis."""
    status: str
    connected: bool
    latency_ms: Optional[float] = None
    used_memory_mb: Optional[float] = None
    connected_clients: Optional[int] = None
    keys_count: Optional[int] = None
    error: Optional[str] = None


class ParserHealth(BaseModel):
    """Статус парсеров."""
    name: str
    status: str
    last_check: Optional[datetime] = None
    response_time_ms: Optional[float] = None
    circuit_breaker_state: Optional[str] = None
    error: Optional[str] = None


class ServiceHealth(BaseModel):
    """Статус сервиса."""
    status: str
    uptime_seconds: Optional[float] = None
    version: str
    environment: str


class DetailedHealthResponse(BaseModel):
    """Развёрнутый ответ health check."""
    overall_status: str
    timestamp: datetime
    database: Optional[DatabaseHealth] = None
    redis: Optional[RedisHealth] = None
    parsers: Optional[list[ParserHealth]] = None
    service: Optional[ServiceHealth] = None
    checks_passed: int = 0
    checks_failed: int = 0
    checks_total: int = 0


# ============================================================================
# Health Check Functions
# ============================================================================

START_TIME = time.time()


async def check_database_health() -> DatabaseHealth:
    """
    Проверить здоровье PostgreSQL.

    Returns:
        DatabaseHealth статус
    """
    start = time.time()

    try:
        # Получаем сессию БД
        db = await get_db_session()

        # Проверяем подключение
        result = await db.execute("SELECT version(), current_setting('server_version_num')")
        row = result.fetchone()

        latency = (time.time() - start) * 1000

        # Получаем статистику подключений
        conn_result = await db.execute("""
            SELECT
                COUNT(*) FILTER (WHERE state = 'active') as active,
                COUNT(*) FILTER (WHERE state = 'idle') as idle
            FROM pg_stat_activity
            WHERE datname = current_database()
        """)
        conn_row = conn_result.fetchone()

        version = row[0] if row else "Unknown"

        return DatabaseHealth(
            status="healthy",
            connected=True,
            latency_ms=round(latency, 2),
            connections_active=conn_row[0] if conn_row else None,
            connections_idle=conn_row[1] if conn_row else None,
            version=version
        )

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return DatabaseHealth(
            status="unhealthy",
            connected=False,
            error=str(e)
        )


async def check_redis_health() -> RedisHealth:
    """
    Проверить здоровье Redis.

    Returns:
        RedisHealth статус
    """
    start = time.time()

    try:
        from app.services.advanced_cache import advanced_cache_manager

        if not advanced_cache_manager.redis_client:
            return RedisHealth(
                status="unhealthy",
                connected=False,
                error="Redis client not initialized"
            )

        # PING тест
        await advanced_cache_manager.redis_client.ping()

        # Получаем информацию
        info = await advanced_cache_manager.redis_client.info("memory", "clients", "stats")

        latency = (time.time() - start) * 1000

        return RedisHealth(
            status="healthy",
            connected=True,
            latency_ms=round(latency, 2),
            used_memory_mb=round(info.get("memory", {}).get("used_memory_human", 0), 2),
            connected_clients=info.get("clients", {}).get("connected_clients", 0),
            keys_count=info.get("stats", {}).get("total_keys", 0)
        )

    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return RedisHealth(
            status="unhealthy",
            connected=False,
            error=str(e)
        )


async def check_parser_health() -> list[ParserHealth]:
    """
    Проверить здоровье парсеров.

    Returns:
        Список статусов парсеров
    """
    from app.utils.circuit_breaker import ParserCircuitBreaker

    parsers = ["AvitoParser", "CianParser", "DomofondParser", "YandexRealtyParser", "DomclickParser"]
    results = []

    for parser_name in parsers:
        try:
            # Получаем circuit breaker статус
            breaker_stats = ParserCircuitBreaker.get_all_stats()

            parser_status = "healthy"
            cb_state = "closed"
            error = None

            if parser_name in breaker_stats:
                stats = breaker_stats[parser_name]
                cb_state = stats.get("state", "unknown")

                if cb_state == "open":
                    parser_status = "unhealthy"
                    error = "Circuit breaker is OPEN"
                elif stats.get("stats", {}).get("consecutive_failures", 0) >= 3:
                    parser_status = "degraded"

            results.append(
                ParserHealth(
                    name=parser_name,
                    status=parser_status,
                    circuit_breaker_state=cb_state,
                    error=error
                )
            )

        except Exception as e:
            logger.error(f"Parser health check failed for {parser_name}: {e}")
            results.append(
                ParserHealth(
                    name=parser_name,
                    status="unhealthy",
                    error=str(e)
                )
            )

    return results


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/health/db")
async def health_check_database() -> DatabaseHealth:
    """
    Проверка здоровья базы данных.

    Returns:
        Статус подключения к PostgreSQL
    """
    return await check_database_health()


@router.get("/health/redis")
async def health_check_redis() -> RedisHealth:
    """
    Проверка здоровья Redis.

    Returns:
        Статус подключения к Redis
    """
    return await check_redis_health()


@router.get("/health/parsers")
async def health_check_parsers() -> list[ParserHealth]:
    """
    Проверка здоровья парсеров.

    Returns:
        Статусы всех парсеров
    """
    return await check_parser_health()


@router.get("/health/detailed")
async def health_check_detailed() -> DetailedHealthResponse:
    """
    Развёрнутая проверка здоровья всех сервисов.

    Проверяет:
    - PostgreSQL (подключение, latency, connections)
    - Redis (подключение, память, клиенты)
    - Парсеры (circuit breaker статусы)
    - Service uptime

    Returns:
        Детальный статус всех сервисов
    """
    # Запускаем все проверки параллельно
    db_health, redis_health, parser_health = await asyncio.gather(
        check_database_health(),
        check_redis_health(),
        check_parser_health(),
        return_exceptions=True
    )

    # Обрабатываем исключения
    if isinstance(db_health, Exception):
        db_health = DatabaseHealth(status="unhealthy", connected=False, error=str(db_health))
    if isinstance(redis_health, Exception):
        redis_health = RedisHealth(status="unhealthy", connected=False, error=str(redis_health))
    if isinstance(parser_health, Exception):
        parser_health = [ParserHealth(name="unknown", status="unhealthy", error=str(parser_health))]

    # Подсчитываем проверки
    checks_passed = 0
    checks_failed = 0

    if db_health.status == "healthy":
        checks_passed += 1
    else:
        checks_failed += 1

    if redis_health.status == "healthy":
        checks_passed += 1
    else:
        checks_failed += 1

    for parser in parser_health:  # type: ignore
        if parser.status == "healthy":
            checks_passed += 1
        else:
            checks_failed += 1

    # Определяем общий статус
    if checks_failed == 0:
        overall_status = "healthy"
    elif checks_passed > 0:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return DetailedHealthResponse(
        overall_status=overall_status,
        timestamp=datetime.utcnow(),
        database=db_health,
        redis=redis_health,
        parsers=parser_health,
        service=ServiceHealth(
            status="healthy",
            uptime_seconds=time.time() - START_TIME,
            version="2.4.0",
            environment="production" if not settings.DEBUG else "development"
        ),
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        checks_total=checks_passed + checks_failed
    )


@router.get("/health")
async def health_check_basic() -> HealthStatus:
    """
    Базовая проверка здоровья.

    Returns:
        Простой статус "ok" если сервис работает
    """
    return HealthStatus(status="ok")


# ============================================================================
# Startup check
# ============================================================================

async def on_startup() -> None:
    """Проверка при старте приложения."""
    logger.info("Running startup health checks...")

    db_health = await check_database_health()
    if db_health.connected:
        logger.info(f"✅ Database connected (latency: {db_health.latency_ms}ms)")
    else:
        logger.warning(f"⚠️  Database not available: {db_health.error}")

    redis_health = await check_redis_health()
    if redis_health.connected:
        logger.info(f"✅ Redis connected (latency: {redis_health.latency_ms}ms)")
    else:
        logger.warning(f"⚠️  Redis not available: {redis_health.error}")

    logger.info("Startup health checks completed")


# ============================================================================
# Export
# ============================================================================

__all__ = [
    "router",
    "check_database_health",
    "check_redis_health",
    "check_parser_health",
    "on_startup",
]
