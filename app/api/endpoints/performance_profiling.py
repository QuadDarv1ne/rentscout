"""
API endpoints for Performance Profiling Tools

Provides detailed performance metrics and bottleneck analysis.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List
from datetime import datetime
from pydantic import BaseModel

from app.utils.performance_profiling import performance_profiler

router = APIRouter()


# ==================== Pydantic Models ====================

class FunctionProfileResponse(BaseModel):
    """Response for function profile"""
    function_name: str
    module_name: str
    call_count: int
    total_time: float
    min_time: float
    max_time: float
    avg_time: float
    calls_per_second: float
    memory_used: int
    memory_peak: int


class FunctionStatistics(BaseModel):
    """Function profiling statistics"""
    total_functions: int
    total_calls: int
    total_time: float
    total_memory: int
    avg_calls_per_function: float


class MemorySummary(BaseModel):
    """Memory profiling summary"""
    current_memory_mb: float
    peak_memory_mb: float
    baseline_memory_mb: float
    trend: str
    snapshots_taken: int


class BottleneckResponse(BaseModel):
    """Performance bottleneck response"""
    function_name: str
    bottleneck_type: str
    severity: str
    current_value: float
    baseline_value: float
    deviation_percent: float
    recommendation: str
    timestamp: str


class ComprehensiveProfile(BaseModel):
    """Comprehensive performance profile"""
    slowest_functions: List[FunctionProfileResponse]
    most_called_functions: List[FunctionProfileResponse]
    memory_hogs: List[FunctionProfileResponse]
    function_statistics: FunctionStatistics
    memory_summary: MemorySummary
    critical_bottlenecks: List[BottleneckResponse]
    recent_bottlenecks: List[BottleneckResponse]
    timestamp: str


# ==================== API Endpoints ====================

@router.get("/api/profiling/functions/slowest")
async def get_slowest_functions(limit: int = Query(10, ge=1, le=50)) -> Dict:
    """
    Get slowest functions by total execution time
    
    Args:
        limit: Number of functions to return
    
    Returns:
        List of slowest functions with profiling data
    """
    try:
        slowest = performance_profiler.function_profiler.get_slowest_functions(limit)
        
        return {
            "count": len(slowest),
            "functions": [
                FunctionProfileResponse(
                    function_name=p.function_name,
                    module_name=p.module_name,
                    call_count=p.call_count,
                    total_time=round(p.total_time, 4),
                    min_time=round(p.min_time if p.min_time != float('inf') else 0, 4),
                    max_time=round(p.max_time, 4),
                    avg_time=round(p.avg_time, 4),
                    calls_per_second=round(p.calls_per_second, 2),
                    memory_used=p.memory_used,
                    memory_peak=p.memory_peak
                )
                for p in slowest
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/profiling/functions/most-called")
async def get_most_called_functions(limit: int = Query(10, ge=1, le=50)) -> Dict:
    """
    Get most frequently called functions
    
    Args:
        limit: Number of functions to return
    
    Returns:
        List of most called functions
    """
    try:
        most_called = performance_profiler.function_profiler.get_most_called_functions(limit)
        
        return {
            "count": len(most_called),
            "functions": [
                FunctionProfileResponse(
                    function_name=p.function_name,
                    module_name=p.module_name,
                    call_count=p.call_count,
                    total_time=round(p.total_time, 4),
                    min_time=round(p.min_time if p.min_time != float('inf') else 0, 4),
                    max_time=round(p.max_time, 4),
                    avg_time=round(p.avg_time, 4),
                    calls_per_second=round(p.calls_per_second, 2),
                    memory_used=p.memory_used,
                    memory_peak=p.memory_peak
                )
                for p in most_called
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/profiling/functions/memory-hogs")
async def get_memory_hogs(limit: int = Query(10, ge=1, le=50)) -> Dict:
    """
    Get functions using most memory
    
    Args:
        limit: Number of functions to return
    
    Returns:
        List of memory-intensive functions
    """
    try:
        hogs = performance_profiler.function_profiler.get_memory_hogs(limit)
        
        return {
            "count": len(hogs),
            "functions": [
                FunctionProfileResponse(
                    function_name=p.function_name,
                    module_name=p.module_name,
                    call_count=p.call_count,
                    total_time=round(p.total_time, 4),
                    min_time=round(p.min_time if p.min_time != float('inf') else 0, 4),
                    max_time=round(p.max_time, 4),
                    avg_time=round(p.avg_time, 4),
                    calls_per_second=round(p.calls_per_second, 2),
                    memory_used=p.memory_used,
                    memory_peak=p.memory_peak
                )
                for p in hogs
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/profiling/functions/statistics")
async def get_function_statistics() -> FunctionStatistics:
    """
    Get overall function profiling statistics
    
    Returns aggregate data about all profiled functions.
    """
    try:
        stats = performance_profiler.function_profiler.get_statistics()
        
        return FunctionStatistics(
            total_functions=stats['total_functions'],
            total_calls=stats['total_calls'],
            total_time=round(stats['total_time'], 4),
            total_memory=stats['total_memory'],
            avg_calls_per_function=round(stats['avg_calls_per_function'], 2)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/profiling/function/{function_key}")
async def get_function_profile(function_key: str) -> FunctionProfileResponse:
    """
    Get profile for specific function
    
    Args:
        function_key: Function identifier (module.function_name)
    
    Returns:
        Profile data for function
    """
    try:
        profile = performance_profiler.function_profiler.get_profile(function_key)
        
        if not profile:
            raise HTTPException(status_code=404, detail=f"No profile for {function_key}")
        
        return FunctionProfileResponse(
            function_name=profile.function_name,
            module_name=profile.module_name,
            call_count=profile.call_count,
            total_time=round(profile.total_time, 4),
            min_time=round(profile.min_time if profile.min_time != float('inf') else 0, 4),
            max_time=round(profile.max_time, 4),
            avg_time=round(profile.avg_time, 4),
            calls_per_second=round(profile.calls_per_second, 2),
            memory_used=profile.memory_used,
            memory_peak=profile.memory_peak
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/profiling/memory/snapshot")
async def take_memory_snapshot(label: str = Query("", description="Label for snapshot")) -> Dict:
    """
    Take memory snapshot
    
    Captures current memory usage for analysis.
    """
    try:
        snapshot = performance_profiler.memory_profiler.take_snapshot(label)
        
        return {
            "label": label,
            "timestamp": snapshot['timestamp'].isoformat(),
            "current_memory_mb": round(snapshot['current_memory'] / 1024 / 1024, 2),
            "peak_memory_mb": round(snapshot['peak_memory'] / 1024 / 1024, 2),
            "delta_from_baseline_mb": round(snapshot['memory_delta_from_baseline'] / 1024 / 1024, 2)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/profiling/memory/summary")
async def get_memory_summary() -> MemorySummary:
    """
    Get memory profiling summary
    
    Returns memory usage statistics and trend.
    """
    try:
        summary = performance_profiler.memory_profiler.get_memory_summary()
        
        if not summary:
            raise HTTPException(status_code=404, detail="No memory snapshots taken")
        
        return MemorySummary(
            current_memory_mb=summary['current_memory_mb'],
            peak_memory_mb=summary['peak_memory_mb'],
            baseline_memory_mb=summary['baseline_memory_mb'],
            trend=summary['trend'],
            snapshots_taken=summary['snapshots_taken']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/profiling/session/start")
async def start_profiling_session(session_name: str = Query(...)) -> Dict:
    """
    Start profiling session
    
    Args:
        session_name: Name of profiling session
    
    Returns:
        Session details
    """
    try:
        performance_profiler.start_session(session_name)
        
        return {
            "status": "started",
            "session_name": session_name,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/profiling/session/end")
async def end_profiling_session(session_name: str = Query(...)) -> Dict:
    """
    End profiling session
    
    Args:
        session_name: Name of profiling session
    
    Returns:
        Session results
    """
    try:
        performance_profiler.end_session(session_name)
        report = performance_profiler.get_session_report(session_name)
        
        if not report:
            raise HTTPException(status_code=404, detail=f"Session {session_name} not found")
        
        return report
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/profiling/bottlenecks/critical")
async def get_critical_bottlenecks() -> Dict:
    """
    Get critical performance bottlenecks
    
    Returns bottlenecks with severity level "critical".
    """
    try:
        critical = performance_profiler.bottleneck_detector.get_critical_bottlenecks()
        
        return {
            "count": len(critical),
            "bottlenecks": [
                {
                    "function_name": b.function_name,
                    "type": b.bottleneck_type,
                    "severity": b.severity,
                    "current_value": round(b.current_value, 2),
                    "baseline_value": round(b.baseline_value, 2),
                    "deviation_percent": round(b.deviation_percent, 2),
                    "recommendation": b.recommendation,
                    "timestamp": b.timestamp.isoformat()
                }
                for b in critical
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/profiling/bottlenecks/recent")
async def get_recent_bottlenecks(limit: int = Query(10, ge=1, le=50)) -> Dict:
    """
    Get recent performance bottlenecks
    
    Args:
        limit: Number of recent bottlenecks to return
    
    Returns:
        List of recently detected bottlenecks
    """
    try:
        recent = performance_profiler.bottleneck_detector.get_recent_bottlenecks(limit)
        
        return {
            "count": len(recent),
            "bottlenecks": [
                {
                    "function_name": b.function_name,
                    "type": b.bottleneck_type,
                    "severity": b.severity,
                    "current_value": round(b.current_value, 2),
                    "baseline_value": round(b.baseline_value, 2),
                    "deviation_percent": round(b.deviation_percent, 2),
                    "recommendation": b.recommendation,
                    "timestamp": b.timestamp.isoformat()
                }
                for b in recent
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/profiling/bottleneck/baseline")
async def set_baseline(
    metric_name: str = Query(..., description="Metric name"),
    baseline_value: float = Query(..., gt=0, description="Baseline value")
) -> Dict:
    """
    Set performance baseline for metric
    
    Used for bottleneck detection.
    """
    try:
        performance_profiler.bottleneck_detector.set_baseline(metric_name, baseline_value)
        
        return {
            "status": "baseline_set",
            "metric_name": metric_name,
            "baseline_value": baseline_value,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/profiling/comprehensive")
async def get_comprehensive_profile() -> Dict:
    """
    Get comprehensive performance profile
    
    Returns complete profiling data including functions, memory, and bottlenecks.
    """
    try:
        profile = performance_profiler.get_comprehensive_profile()
        
        return {
            **profile,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/profiling/health")
async def profiling_health() -> Dict:
    """
    Check health of profiling system
    
    Returns status and statistics.
    """
    stats = performance_profiler.function_profiler.get_statistics()
    
    return {
        "status": "healthy",
        "system": "performance_profiler",
        "version": "1.0",
        "functions_profiled": stats['total_functions'],
        "total_calls": stats['total_calls'],
        "total_time_seconds": round(stats['total_time'], 2),
        "memory_sessions": len(performance_profiler.memory_profiler.memory_snapshots),
        "timestamp": datetime.now().isoformat()
    }
