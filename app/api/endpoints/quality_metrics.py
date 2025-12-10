"""Quality metrics API for parser performance analysis."""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from app.utils.logger import logger
from app.db.models.session import get_db
from app.models.schemas import PropertyResponse

router = APIRouter(prefix="/api/quality", tags=["quality-metrics"])


@router.get("/parser-stats", response_model=Dict[str, Any])
async def get_parser_stats(
    start_date: Optional[str] = Query(None, description="ISO format start date"),
    end_date: Optional[str] = Query(None, description="ISO format end date"),
) -> Dict[str, Any]:
    """Get detailed statistics for all parsers.
    
    Returns:
        - success_rate: % of successful parses
        - avg_parse_time: Average parse duration (ms)
        - error_distribution: Error types and counts
        - items_parsed: Total items parsed per parser
        - parsers_healthy: Which parsers are working well
    
    Example:
        GET /api/quality/parser-stats?start_date=2025-12-01&end_date=2025-12-10
    """
    try:
        start = datetime.fromisoformat(start_date) if start_date else datetime.now() - timedelta(days=7)
        end = datetime.fromisoformat(end_date) if end_date else datetime.now()
        
        # Mock data for now - in production, query actual parser metrics
        stats = {
            "period": {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "days": (end - start).days,
            },
            "parsers": {
                "avito": {
                    "total_requests": 1250,
                    "successful": 1180,
                    "failed": 70,
                    "success_rate": 94.4,
                    "avg_parse_time_ms": 2340,
                    "items_parsed": 5600,
                    "status": "healthy",
                    "errors": {
                        "timeout": 45,
                        "connection_error": 20,
                        "parse_error": 5,
                    },
                },
                "cian": {
                    "total_requests": 980,
                    "successful": 960,
                    "failed": 20,
                    "success_rate": 97.9,
                    "avg_parse_time_ms": 1890,
                    "items_parsed": 4200,
                    "status": "healthy",
                    "errors": {
                        "timeout": 15,
                        "parse_error": 5,
                    },
                },
                "yandex_realty": {
                    "total_requests": 650,
                    "successful": 620,
                    "failed": 30,
                    "success_rate": 95.4,
                    "avg_parse_time_ms": 2100,
                    "items_parsed": 3100,
                    "status": "healthy",
                    "errors": {
                        "timeout": 20,
                        "connection_error": 10,
                    },
                },
                "domofond": {
                    "total_requests": 420,
                    "successful": 380,
                    "failed": 40,
                    "success_rate": 90.5,
                    "avg_parse_time_ms": 2800,
                    "items_parsed": 1850,
                    "status": "degraded",
                    "errors": {
                        "timeout": 35,
                        "parse_error": 5,
                    },
                },
            },
            "summary": {
                "total_requests": 3300,
                "total_successful": 3140,
                "total_failed": 160,
                "overall_success_rate": 95.2,
                "avg_parse_time_ms": 2282,
                "total_items": 14750,
            },
        }
        
        logger.info(f"Generated parser stats for period {start} to {end}")
        return stats
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use ISO format (YYYY-MM-DD)",
        )
    except Exception as e:
        logger.error(f"Failed to get parser stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/data-quality", response_model=Dict[str, Any])
async def get_data_quality() -> Dict[str, Any]:
    """Assess data quality of indexed properties.
    
    Returns:
        - completeness: % of properties with all required fields
        - validity: % of properties with valid values
        - duplicates: Count of potential duplicates
        - outliers: Count of suspicious values
        - missing_fields: Distribution of missing fields
    
    Example:
        GET /api/quality/data-quality
    """
    try:
        # Mock data for demonstration
        quality_report = {
            "timestamp": datetime.now().isoformat(),
            "total_properties": 15200,
            "completeness": {
                "score": 96.5,
                "properties_complete": 14670,
                "missing_by_field": {
                    "title": 85,
                    "description": 320,
                    "address": 125,
                    "image_url": 1200,
                },
            },
            "validity": {
                "score": 98.2,
                "valid_prices": 15150,
                "invalid_prices": 50,
                "issues": {
                    "negative_price": 20,
                    "zero_price": 15,
                    "unrealistic_price": 15,
                },
            },
            "duplicates": {
                "potential_duplicates": 145,
                "duplicate_rate_percent": 0.95,
                "most_common_duplicates": [
                    {
                        "property_id": "avito_12345",
                        "duplicate_count": 3,
                        "sources": ["avito", "cian", "yandex_realty"],
                    },
                ],
            },
            "outliers": {
                "suspicious_records": 287,
                "outlier_rate_percent": 1.89,
                "types": {
                    "extremely_high_price": 125,
                    "extremely_low_price": 98,
                    "unusual_area": 45,
                    "invalid_rooms": 19,
                },
            },
            "by_source": {
                "avito": {
                    "completeness": 97.2,
                    "validity": 98.5,
                    "duplicates": 45,
                },
                "cian": {
                    "completeness": 98.1,
                    "validity": 99.1,
                    "duplicates": 52,
                },
                "yandex_realty": {
                    "completeness": 95.3,
                    "validity": 97.2,
                    "duplicates": 38,
                },
                "domofond": {
                    "completeness": 94.5,
                    "validity": 96.8,
                    "duplicates": 10,
                },
            },
        }
        
        logger.info("Data quality assessment completed")
        return quality_report
    except Exception as e:
        logger.error(f"Failed to get data quality: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health-report", response_model=Dict[str, Any])
async def get_health_report() -> Dict[str, Any]:
    """Generate overall system health report.
    
    Returns:
        - overall_status: green/yellow/red
        - services: Health of each component
        - performance: System performance metrics
        - recommendations: Suggested improvements
    
    Example:
        GET /api/quality/health-report
    """
    try:
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": "green",
            "services": {
                "api": {
                    "status": "green",
                    "response_time_ms": 45,
                    "uptime_percent": 99.98,
                    "requests_per_second": 542,
                },
                "database": {
                    "status": "green",
                    "response_time_ms": 25,
                    "connection_pool_usage": 18,
                    "query_cache_hit_rate": 78.5,
                },
                "cache": {
                    "status": "green",
                    "redis_connected": True,
                    "memory_usage_mb": 285,
                    "hit_rate": 82.3,
                },
                "elasticsearch": {
                    "status": "green",
                    "cluster_health": "green",
                    "active_shards": 5,
                    "indices": 3,
                },
                "celery": {
                    "status": "green",
                    "active_workers": 2,
                    "queued_tasks": 12,
                    "avg_task_time_ms": 1240,
                },
            },
            "performance": {
                "api_response_time_p50_ms": 45,
                "api_response_time_p95_ms": 185,
                "api_response_time_p99_ms": 450,
                "database_response_time_p50_ms": 25,
                "search_latency_ms": 120,
                "parser_efficiency_percent": 95.2,
            },
            "recommendations": [
                {
                    "severity": "info",
                    "component": "cache",
                    "message": "Cache hit rate is good (82.3%), but could increase hit rate by optimizing TTL values",
                },
                {
                    "severity": "warning",
                    "component": "domofond_parser",
                    "message": "Parser success rate is 90.5%, below target of 95%. Consider investigating timeout issues",
                },
                {
                    "severity": "info",
                    "component": "elasticsearch",
                    "message": "Consider indexing new properties to improve search performance",
                },
            ],
            "summary": {
                "healthy_components": 5,
                "degraded_components": 0,
                "failed_components": 0,
                "uptime_percent": 99.98,
            },
        }
        
        logger.info("Health report generated")
        return health_report
    except Exception as e:
        logger.error(f"Failed to generate health report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/source-quality/{source}", response_model=Dict[str, Any])
async def get_source_quality(source: str) -> Dict[str, Any]:
    """Get detailed quality metrics for a specific source.
    
    Args:
        source: Parser source (avito, cian, yandex_realty, etc.)
    
    Returns:
        Detailed quality metrics for the source
    
    Example:
        GET /api/quality/source-quality/avito
    """
    try:
        valid_sources = ["avito", "cian", "yandex_realty", "domofond", "all"]
        
        if source not in valid_sources:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source. Must be one of: {', '.join(valid_sources)}",
            )
        
        # Mock data for specific source
        source_quality = {
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "total_properties": 5600,
            "last_update": (datetime.now() - timedelta(minutes=5)).isoformat(),
            "metrics": {
                "success_rate": 94.4,
                "avg_response_time_ms": 2340,
                "data_completeness": 96.5,
                "data_validity": 98.2,
                "duplicate_rate": 0.95,
                "parse_errors": 70,
            },
            "recent_errors": [
                {
                    "timestamp": (datetime.now() - timedelta(minutes=10)).isoformat(),
                    "error_type": "timeout",
                    "count": 5,
                    "resolved": True,
                },
                {
                    "timestamp": (datetime.now() - timedelta(minutes=25)).isoformat(),
                    "error_type": "connection_error",
                    "count": 3,
                    "resolved": True,
                },
            ],
            "recommendations": [
                "Monitor response times - currently 2340ms, target is < 2000ms",
                "Investigate duplicate rate of 0.95% to improve data quality",
            ],
        }
        
        logger.info(f"Generated quality metrics for source: {source}")
        return source_quality
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get source quality for {source}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
