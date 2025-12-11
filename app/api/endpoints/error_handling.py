"""
Error handling and diagnostics API endpoints.

Provides endpoints for monitoring parser errors, circuit breaker status,
and error recovery strategies.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, Optional
from datetime import datetime

from app.utils.error_handling import (
    error_tracker,
    circuit_breaker,
    ErrorType,
    ErrorSeverity
)
from app.utils.logger import logger

router = APIRouter(prefix="/api/errors", tags=["error-handling"])


@router.get("/health")
async def error_system_health() -> Dict[str, str]:
    """
    Check error handling system health.
    
    Returns:
        - status: System health status
        - circuit_breaker_state: Current circuit breaker state
    """
    return {
        "status": "operational",
        "circuit_breaker_state": circuit_breaker.state.value,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/summary")
async def get_error_summary() -> Dict[str, Any]:
    """
    Get comprehensive error tracking summary.
    
    Returns:
        - total_errors: Total errors recorded
        - critical/high/medium/low: Error counts by severity
        - top_errors: Most common errors
        - recovery_rate: Estimated recovery success rate
    """
    try:
        summary = error_tracker.get_summary()
        return {
            **summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get error summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get error summary")


@router.get("/top-errors")
async def get_top_errors(
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    """
    Get most common errors.
    
    Args:
        limit: Number of errors to return (1-50)
    
    Returns:
        List of error summaries with frequency and affected sources
    """
    try:
        top_errors = error_tracker.get_top_errors(limit)
        return {
            "total_tracked": len(error_tracker.errors),
            "top_errors": top_errors,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get top errors: {e}")
        raise HTTPException(status_code=500, detail="Failed to get top errors")


@router.get("/by-source/{source}")
async def get_errors_by_source(
    source: str,
    error_type: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get errors for specific parser source.
    
    Args:
        source: Parser source name (e.g., 'avito', 'cian')
        error_type: Filter by error type (optional)
        limit: Number of errors to return
    
    Returns:
        List of errors with details
    """
    try:
        source_errors = [e for e in error_tracker.errors if e.source == source]
        
        if error_type:
            source_errors = [e for e in source_errors if e.error_type.value == error_type]
        
        # Sort by timestamp descending
        source_errors.sort(key=lambda e: e.timestamp, reverse=True)
        
        # Get error rate
        error_rate = error_tracker.get_error_rate(source)
        
        return {
            "source": source,
            "error_count": len(source_errors),
            "error_rate_percent": round(error_rate, 2),
            "errors": [e.to_dict() for e in source_errors[:limit]],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get source errors: {e}")
        raise HTTPException(status_code=500, detail="Failed to get source errors")


@router.get("/by-type/{error_type}")
async def get_errors_by_type(
    error_type: str,
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get all errors of specific type.
    
    Args:
        error_type: Error type ('network', 'parsing', 'validation', etc.)
        limit: Number of errors to return
    
    Returns:
        List of errors matching type
    """
    try:
        # Validate error type
        valid_types = {e.value for e in ErrorType}
        if error_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid error_type. Valid: {valid_types}"
            )
        
        typed_errors = [
            e for e in error_tracker.errors
            if e.error_type.value == error_type
        ]
        
        # Sort by timestamp descending
        typed_errors.sort(key=lambda e: e.timestamp, reverse=True)
        
        return {
            "error_type": error_type,
            "count": len(typed_errors),
            "errors": [e.to_dict() for e in typed_errors[:limit]],
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get errors by type: {e}")
        raise HTTPException(status_code=500, detail="Failed to get errors by type")


@router.get("/by-severity/{severity}")
async def get_errors_by_severity(
    severity: str,
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get all errors of specific severity.
    
    Args:
        severity: Severity level ('low', 'medium', 'high', 'critical')
        limit: Number of errors to return
    
    Returns:
        List of errors matching severity
    """
    try:
        # Validate severity
        valid_severities = {s.value for s in ErrorSeverity}
        if severity not in valid_severities:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid severity. Valid: {valid_severities}"
            )
        
        severity_errors = [
            e for e in error_tracker.errors
            if e.severity.value == severity
        ]
        
        # Sort by timestamp descending
        severity_errors.sort(key=lambda e: e.timestamp, reverse=True)
        
        return {
            "severity": severity,
            "count": len(severity_errors),
            "errors": [e.to_dict() for e in severity_errors[:limit]],
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get errors by severity: {e}")
        raise HTTPException(status_code=500, detail="Failed to get errors by severity")


@router.get("/circuit-breaker/status")
async def get_circuit_breaker_status() -> Dict[str, Any]:
    """
    Get circuit breaker status.
    
    Returns:
        - state: Circuit breaker state ('closed', 'open', 'half_open')
        - failure_count: Current failure count
        - success_count: Current success count
        - last_failure: Timestamp of last failure
    """
    try:
        status = circuit_breaker.get_status()
        return {
            **status,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get circuit breaker status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get circuit breaker status")


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker() -> Dict[str, Any]:
    """
    Manually reset circuit breaker.
    
    Use with caution - resets failure counters and closes the circuit.
    """
    try:
        circuit_breaker.failure_count = 0
        circuit_breaker.success_count = 0
        circuit_breaker.state = circuit_breaker.state.__class__.CLOSED
        
        logger.info("Circuit breaker manually reset")
        
        return {
            "status": "reset",
            "state": circuit_breaker.state.value,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset circuit breaker")


@router.get("/recommendations")
async def get_error_recommendations() -> Dict[str, Any]:
    """
    Get recommendations based on error patterns.
    
    Analyzes error history and suggests improvements
    for parser reliability and error handling.
    
    Returns:
        - issues: Identified issues
        - recommendations: Suggested improvements
        - priority: Priority of implementation
    """
    try:
        summary = error_tracker.get_summary()
        top_errors = error_tracker.get_top_errors(3)
        
        recommendations = []
        priority = "low"
        
        # Check critical errors
        if summary.get('critical', 0) > 0:
            recommendations.append({
                'issue': 'Critical errors detected',
                'suggestion': 'Investigate and fix critical parsing issues immediately',
                'priority': 'critical'
            })
            priority = "critical"
        
        # Check high severity
        if summary.get('high', 0) > 5:
            recommendations.append({
                'issue': 'High severity errors',
                'suggestion': 'Review error logs and implement recovery strategies',
                'priority': 'high'
            })
            if priority == 'low':
                priority = 'high'
        
        # Check error rate
        if summary.get('total_errors', 0) > 100:
            avg_error_type = top_errors[0]['type'] if top_errors else 'unknown'
            recommendations.append({
                'issue': f'High error rate ({avg_error_type})',
                'suggestion': f'Implement specific handling for {avg_error_type} errors',
                'priority': 'high'
            })
        
        # Check unrecoverable errors
        if summary.get('unrecoverable', 0) > summary.get('recoverable', 0):
            recommendations.append({
                'issue': 'More unrecoverable than recoverable errors',
                'suggestion': 'Improve validation and error handling logic',
                'priority': 'medium'
            })
        
        return {
            "summary": summary,
            "recommendations": recommendations,
            "overall_priority": priority,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recommendations")


@router.post("/clear-history")
async def clear_error_history() -> Dict[str, str]:
    """
    Clear error history.
    
    ⚠️ Warning: This will permanently delete all error records!
    """
    try:
        error_count = len(error_tracker.errors)
        error_tracker.errors.clear()
        error_tracker._error_counts.clear()
        
        logger.warning(f"Error history cleared ({error_count} errors deleted)")
        
        return {
            "status": "success",
            "message": f"Cleared {error_count} error records",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to clear error history: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear error history")


@router.get("/stats")
async def get_error_statistics() -> Dict[str, Any]:
    """
    Get detailed error statistics.
    
    Returns:
        - errors_per_source: Error counts by parser source
        - errors_per_type: Error counts by type
        - errors_per_severity: Error counts by severity
        - recovery_rate: Estimated recovery success
    """
    try:
        stats = {
            'errors_per_source': {},
            'errors_per_type': {},
            'errors_per_severity': {},
            'total_errors': len(error_tracker.errors),
        }
        
        # Count by source
        for error in error_tracker.errors:
            source = error.source
            stats['errors_per_source'][source] = stats['errors_per_source'].get(source, 0) + 1
        
        # Count by type
        for error in error_tracker.errors:
            type_name = error.error_type.value
            stats['errors_per_type'][type_name] = stats['errors_per_type'].get(type_name, 0) + 1
        
        # Count by severity
        for error in error_tracker.errors:
            severity = error.severity.value
            stats['errors_per_severity'][severity] = stats['errors_per_severity'].get(severity, 0) + 1
        
        return {
            **stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get error statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get error statistics")
