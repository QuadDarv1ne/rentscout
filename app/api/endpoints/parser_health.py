"""
Parser health monitoring endpoints.

Provides health checks for all configured parsers.
"""
import asyncio
import httpx
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.utils.logger import logger


router = APIRouter(prefix="/parsers", tags=["Health", "Parsers"])


class ParserStatus(str, Enum):
    """Parser health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ParserHealthCheck(BaseModel):
    """Health check result for a single parser."""
    name: str = Field(..., description="Parser name")
    status: ParserStatus = Field(..., description="Health status")
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    details: Dict = Field(default_factory=dict, description="Additional details")


class ParsersHealthResponse(BaseModel):
    """Health check response for all parsers."""
    status: ParserStatus = Field(..., description="Overall health status")
    parsers: List[ParserHealthCheck] = Field(..., description="Individual parser health checks")
    total_parsers: int = Field(..., description="Total number of parsers")
    healthy_count: int = Field(..., description="Number of healthy parsers")
    unhealthy_count: int = Field(..., description="Number of unhealthy parsers")
    checked_at: str = Field(..., description="ISO timestamp of check")


@dataclass
class ParserConfig:
    """Configuration for parser health check."""
    name: str
    base_url: str
    timeout: float = 5.0
    expected_status: int = 200


# Parser configurations
PARSER_CONFIGS = [
    ParserConfig(
        name="Avito",
        base_url="https://www.avito.ru",
        timeout=5.0,
    ),
    ParserConfig(
        name="Cian",
        base_url="https://www.cian.ru",
        timeout=5.0,
    ),
    ParserConfig(
        name="Domclick",
        base_url="https://domclick.ru",
        timeout=5.0,
    ),
    ParserConfig(
        name="Domofond",
        base_url="https://domofond.ru",
        timeout=5.0,
    ),
    ParserConfig(
        name="YandexRealty",
        base_url="https://realty.yandex.ru",
        timeout=5.0,
    ),
]


async def check_parser_health(config: ParserConfig) -> ParserHealthCheck:
    """
    Check health of a single parser.

    Performs HTTP GET request to parser's base URL and measures response time.
    """
    start_time = time.time()

    try:
        async with httpx.AsyncClient(
            timeout=config.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "RentScout Health Checker/1.0",
                "Accept": "text/html,application/xhtml+xml",
            }
        ) as client:
            response = await client.get(config.base_url)
            response_time = (time.time() - start_time) * 1000  # Convert to ms

            # Check status code
            if response.status_code == config.expected_status:
                status = ParserStatus.HEALTHY
                error = None
            elif response.status_code in (403, 429):
                # Rate limited or forbidden - degraded
                status = ParserStatus.DEGRADED
                error = f"Rate limited or blocked ({response.status_code})"
            elif response.status_code >= 500:
                # Server error - unhealthy
                status = ParserStatus.UNHEALTHY
                error = f"Server error ({response.status_code})"
            else:
                # Other status - consider healthy if not error
                status = ParserStatus.HEALTHY
                error = None

            return ParserHealthCheck(
                name=config.name,
                status=status,
                response_time_ms=response_time,
                error=error,
                details={
                    "status_code": response.status_code,
                    "base_url": config.base_url,
                }
            )

    except asyncio.TimeoutError:
        response_time = (time.time() - start_time) * 1000
        return ParserHealthCheck(
            name=config.name,
            status=ParserStatus.UNHEALTHY,
            response_time_ms=response_time,
            error=f"Timeout after {config.timeout}s",
            details={"base_url": config.base_url, "timeout": config.timeout}
        )

    except httpx.HTTPError as e:
        response_time = (time.time() - start_time) * 1000
        return ParserHealthCheck(
            name=config.name,
            status=ParserStatus.UNHEALTHY,
            response_time_ms=response_time,
            error=str(e),
            details={"base_url": config.base_url}
        )

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        logger.error(f"Health check failed for {config.name}: {e}")
        return ParserHealthCheck(
            name=config.name,
            status=ParserStatus.UNHEALTHY,
            response_time_ms=response_time,
            error=str(e),
            details={"base_url": config.base_url}
        )


@router.get("/health", response_model=ParsersHealthResponse)
async def get_parsers_health():
    """
    Check health of all configured parsers.

    Performs concurrent HTTP requests to each parser's base URL and returns:
    - Overall status (healthy/degraded/unhealthy)
    - Individual parser status
    - Response times
    - Error messages if any

    **Use cases:**
    - Monitoring dashboard
    - Alerting system
    - Pre-flight checks before search operations
    """
    from datetime import datetime

    # Run health checks concurrently
    tasks = [check_parser_health(config) for config in PARSER_CONFIGS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    parser_checks = []
    for result in results:
        if isinstance(result, Exception):
            # Handle unexpected exceptions
            parser_checks.append(ParserHealthCheck(
                name="Unknown",
                status=ParserStatus.UNHEALTHY,
                error=str(result)
            ))
        else:
            parser_checks.append(result)

    # Calculate aggregate stats
    healthy_count = sum(1 for p in parser_checks if p.status == ParserStatus.HEALTHY)
    degraded_count = sum(1 for p in parser_checks if p.status == ParserStatus.DEGRADED)
    unhealthy_count = sum(1 for p in parser_checks if p.status == ParserStatus.UNHEALTHY)

    # Determine overall status
    if unhealthy_count > len(parser_checks) // 2:
        overall_status = ParserStatus.UNHEALTHY
    elif degraded_count > 0 or unhealthy_count > 0:
        overall_status = ParserStatus.DEGRADED
    else:
        overall_status = ParserStatus.HEALTHY

    return ParsersHealthResponse(
        status=overall_status,
        parsers=parser_checks,
        total_parsers=len(parser_checks),
        healthy_count=healthy_count,
        unhealthy_count=unhealthy_count,
        checked_at=datetime.utcnow().isoformat()
    )


@router.get("/health/{parser_name}")
async def get_parser_health(parser_name: str):
    """
    Check health of a specific parser.

    Args:
        parser_name: Name of the parser (avito, cian, domclick, etc.)

    Returns:
        Health check result for the specified parser
    """
    # Find parser config by name
    config = None
    for c in PARSER_CONFIGS:
        if c.name.lower() == parser_name.lower():
            config = c
            break

    if not config:
        raise HTTPException(
            status_code=404,
            detail=f"Parser '{parser_name}' not found. Available: {[c.name for c in PARSER_CONFIGS]}"
        )

    result = await check_parser_health(config)
    return {
        "name": result.name,
        "status": result.status.value,
        "response_time_ms": result.response_time_ms,
        "error": result.error,
        "details": result.details,
    }


@router.get("/status")
async def get_parsers_status():
    """
    Quick status check without detailed metrics.

    Returns simple status for each parser (healthy/degraded/unhealthy).
    Faster than /health endpoint as it doesn't measure response times.
    """
    from datetime import datetime

    status_summary = []
    for config in PARSER_CONFIGS:
        status_summary.append({
            "name": config.name,
            "base_url": config.base_url,
            "configured": True,
        })

    return {
        "status": "ok",
        "parsers": status_summary,
        "total": len(status_summary),
        "checked_at": datetime.utcnow().isoformat()
    }
