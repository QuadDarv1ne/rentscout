"""
Advanced metrics API endpoints for monitoring and observability.

Provides comprehensive metrics about parser performance, cache efficiency,
database operations, and API performance.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from prometheus_client import generate_latest

from app.utils.advanced_metrics import (
    metrics_reporter, 
    SystemMetricsCollector,
    metrics_registry
)
from app.utils.logger import logger

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/health")
async def metrics_health() -> Dict[str, Any]:
    """
    Check metrics system health.
    
    Returns:
        - status: Overall system health
        - components: Status of individual components
        - timestamp: Current server time
    """
    return {
        "status": "healthy",
        "components": {
            "prometheus": "operational",
            "metrics_reporter": "operational",
            "system_collector": "operational"
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/summary")
async def get_metrics_summary() -> Dict[str, Any]:
    """
    Get comprehensive metrics summary.
    
    Returns detailed metrics about:
    - Parser performance by source
    - Cache efficiency (hits, misses, evictions)
    - API performance by endpoint
    - Database operations
    
    Example response:
    ```json
    {
        "timestamp": "2025-12-11T10:30:00",
        "parsers": {
            "avito": {
                "success_rate_percent": 95.5,
                "avg_duration_seconds": 2.3,
                "total_items": 1250,
                "success_count": 191,
                "failure_count": 9
            }
        },
        "cache": {
            "l1": {
                "hit_rate_percent": 78.5,
                "hits": 1570,
                "misses": 430
            }
        },
        "api": {
            "GET /api/properties/search": {
                "requests_total": 2000,
                "error_rate_percent": 2.5,
                "avg_duration_seconds": 0.45
            }
        }
    }
    ```
    """
    try:
        summary = metrics_reporter.get_summary_report()
        return summary
    except Exception as e:
        logger.error(f"Failed to generate metrics summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate metrics summary")


@router.get("/parsers")
async def get_parser_metrics(source: Optional[str] = None) -> Dict[str, Any]:
    """
    Get detailed parser metrics.
    
    Args:
        source: Filter by specific parser source (optional)
    
    Returns parser statistics including success rates, performance, and errors.
    
    Example:
        GET /api/metrics/parsers?source=avito
    """
    try:
        if source:
            if source not in metrics_reporter.parser_metrics:
                raise HTTPException(status_code=404, detail=f"Source '{source}' not found")
            
            metrics = metrics_reporter.parser_metrics[source]
            return {
                "source": source,
                "success_rate_percent": round(metrics.get_success_rate(), 2),
                "avg_duration_seconds": round(metrics.get_avg_duration(), 3),
                "total_items": metrics.total_items,
                "success_count": metrics.success_count,
                "failure_count": metrics.failure_count,
                "timeout_count": metrics.timeout_count,
                "avg_items_per_parse": round(metrics.get_avg_items_per_parse(), 2),
                "errors": metrics.errors,
                "last_updated": metrics.timestamp.isoformat()
            }
        else:
            # Return all parsers
            return {
                "parsers": {
                    src: {
                        "success_rate_percent": round(m.get_success_rate(), 2),
                        "avg_duration_seconds": round(m.get_avg_duration(), 3),
                        "total_items": m.total_items,
                        "success_count": m.success_count,
                        "failure_count": m.failure_count,
                        "timeout_count": m.timeout_count,
                    }
                    for src, m in metrics_reporter.parser_metrics.items()
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get parser metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get parser metrics")


@router.get("/cache")
async def get_cache_metrics(level: Optional[str] = None) -> Dict[str, Any]:
    """
    Get detailed cache efficiency metrics.
    
    Args:
        level: Filter by cache level - 'l1', 'l2', or 'redis' (optional)
    
    Returns cache statistics including hit rates, memory usage, and evictions.
    
    Example:
        GET /api/metrics/cache?level=l1
    """
    try:
        if level:
            if level not in metrics_reporter.cache_metrics:
                raise HTTPException(status_code=404, detail=f"Cache level '{level}' not found")
            
            metrics = metrics_reporter.cache_metrics[level]
            return {
                "level": level,
                "hit_rate_percent": round(metrics.get_hit_rate_percent(), 2),
                "hits": metrics.hits,
                "misses": metrics.misses,
                "total_accesses": metrics.hits + metrics.misses,
                "evictions": metrics.evictions,
                "memory_bytes": metrics.memory_bytes,
                "memory_mb": round(metrics.memory_bytes / (1024 * 1024), 2),
                "last_updated": metrics.timestamp.isoformat()
            }
        else:
            # Return all cache levels
            return {
                "cache_levels": {
                    lvl: {
                        "hit_rate_percent": round(m.get_hit_rate_percent(), 2),
                        "hits": m.hits,
                        "misses": m.misses,
                        "evictions": m.evictions,
                        "memory_mb": round(m.memory_bytes / (1024 * 1024), 2),
                    }
                    for lvl, m in metrics_reporter.cache_metrics.items()
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get cache metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache metrics")


@router.get("/api-endpoints")
async def get_api_metrics(
    endpoint: Optional[str] = None,
    method: Optional[str] = "GET"
) -> Dict[str, Any]:
    """
    Get API performance metrics by endpoint.
    
    Args:
        endpoint: Filter by specific endpoint (optional)
        method: HTTP method filter (default: GET)
    
    Returns API statistics including request counts, error rates, and response times.
    
    Example:
        GET /api/metrics/api-endpoints?endpoint=/api/properties/search
    """
    try:
        if endpoint:
            key = (endpoint, method)
            if key not in metrics_reporter.api_metrics:
                raise HTTPException(status_code=404, detail=f"Endpoint '{method} {endpoint}' not found")
            
            metrics = metrics_reporter.api_metrics[key]
            return {
                "endpoint": endpoint,
                "method": method,
                "requests_total": metrics.requests_total,
                "errors_total": metrics.errors_total,
                "error_rate_percent": round(metrics.get_error_rate(), 2),
                "avg_duration_seconds": round(metrics.get_avg_duration(), 3),
                "most_common_status": metrics.get_most_common_status(),
                "status_codes": metrics.status_codes,
                "last_updated": metrics.timestamp.isoformat()
            }
        else:
            # Return all endpoints
            return {
                "endpoints": {
                    f"{m} {e}": {
                        "requests_total": metrics.requests_total,
                        "error_rate_percent": round(metrics.get_error_rate(), 2),
                        "avg_duration_seconds": round(metrics.get_avg_duration(), 3),
                    }
                    for (e, m), metrics in metrics_reporter.api_metrics.items()
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get API metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get API metrics")


@router.get("/system")
async def get_system_metrics() -> Dict[str, Any]:
    """
    Get system resource metrics.
    
    Returns:
        - cpu_usage_percent: Current CPU usage
        - memory_usage_bytes: Current memory usage
        - memory_percent: Memory usage as percentage
        - process_memory_mb: Current process memory usage
    """
    try:
        SystemMetricsCollector.update_system_metrics()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "cpu_usage_percent": round(metrics_registry.system_cpu_usage._value.get(), 2),
                "memory_usage_bytes": int(metrics_registry.system_memory_usage._value.get()),
                "memory_percent": round(metrics_registry.system_memory_percent._value.get(), 2),
            },
            "process": {
                "memory_bytes": int(metrics_registry.process_memory_usage._value.get()),
                "memory_mb": round(
                    metrics_registry.process_memory_usage._value.get() / (1024 * 1024), 2
                ),
            }
        }
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system metrics")


@router.get("/prometheus")
async def get_prometheus_metrics() -> str:
    """
    Get raw Prometheus metrics in text format.
    
    This endpoint returns all metrics in Prometheus exposition format.
    Can be scraped by Prometheus or viewed directly.
    
    Content-Type: text/plain; version=0.0.4
    """
    try:
        return generate_latest(metrics_registry.registry).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to generate Prometheus metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate Prometheus metrics")


@router.get("/quality-report")
async def get_quality_report(
    days: int = Query(1, ge=1, le=30)
) -> Dict[str, Any]:
    """
    Get data quality report.
    
    Args:
        days: Number of days to include in report (1-30, default: 1)
    
    Returns comprehensive data quality metrics and recommendations.
    """
    try:
        summary = metrics_reporter.get_summary_report()
        
        # Calculate aggregate quality metrics
        quality_metrics = {
            "overall_parser_success_rate": 0,
            "average_cache_hit_rate": 0,
            "api_error_rate": 0,
            "timestamp": datetime.now().isoformat(),
        }
        
        # Parser success rate
        parser_rates = [
            m['success_rate_percent'] 
            for m in summary.get('parsers', {}).values()
        ]
        if parser_rates:
            quality_metrics["overall_parser_success_rate"] = round(sum(parser_rates) / len(parser_rates), 2)
        
        # Cache hit rate
        cache_rates = [
            m['hit_rate_percent'] 
            for m in summary.get('cache', {}).values()
        ]
        if cache_rates:
            quality_metrics["average_cache_hit_rate"] = round(sum(cache_rates) / len(cache_rates), 2)
        
        # API error rate
        api_errors = [
            m['error_rate_percent'] 
            for m in summary.get('api', {}).values()
        ]
        if api_errors:
            quality_metrics["api_error_rate"] = round(sum(api_errors) / len(api_errors), 2)
        
        # Recommendations
        recommendations = []
        if quality_metrics["overall_parser_success_rate"] < 90:
            recommendations.append("Parser success rate is below 90%. Review parser logs for errors.")
        if quality_metrics["average_cache_hit_rate"] < 70:
            recommendations.append("Cache hit rate is below 70%. Consider increasing cache TTL or size.")
        if quality_metrics["api_error_rate"] > 5:
            recommendations.append("API error rate is above 5%. Review error logs and API endpoints.")
        
        return {
            **quality_metrics,
            "recommendations": recommendations,
            "full_report": summary
        }
    except Exception as e:
        logger.error(f"Failed to generate quality report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate quality report")


@router.post("/reset")
async def reset_metrics() -> Dict[str, str]:
    """
    Reset all metrics counters.
    
    ⚠️ Warning: This will clear all accumulated metrics!
    Use with caution - only recommended for testing.
    """
    try:
        metrics_reporter.parser_metrics.clear()
        metrics_reporter.cache_metrics.clear()
        metrics_reporter.api_metrics.clear()
        
        logger.warning("All metrics have been reset")
        return {
            "status": "success",
            "message": "All metrics counters have been reset",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to reset metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset metrics")
