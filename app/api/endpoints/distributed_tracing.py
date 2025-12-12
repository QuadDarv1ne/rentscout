"""
API endpoints for OpenTelemetry Distributed Tracing

Provides access to trace data, span information, and tracing statistics.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel

from app.core.tracing import tracer, SpanKind

router = APIRouter()


# ==================== Pydantic Models ====================

class SpanEventResponse(BaseModel):
    """Response model for span event"""
    name: str
    timestamp: str
    attributes: Dict[str, Any]


class SpanLinkResponse(BaseModel):
    """Response model for span link"""
    trace_id: str
    span_id: str
    attributes: Dict[str, Any]


class SpanResponse(BaseModel):
    """Response model for span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    kind: str
    start_time: str
    end_time: Optional[str]
    duration_ms: float
    status: str
    attributes: Dict[str, Any]
    events: List[SpanEventResponse]
    links: List[SpanLinkResponse]


class TraceResponse(BaseModel):
    """Response model for complete trace"""
    trace_id: str
    span_count: int
    total_duration_ms: float
    start_time: str
    end_time: Optional[str]
    status: str
    spans: List[SpanResponse]


class ActiveTraceResponse(BaseModel):
    """Response model for active trace"""
    trace_id: str
    span_count: int
    active_spans: int
    duration_ms: float


class TracerStatsResponse(BaseModel):
    """Response model for tracer statistics"""
    active_traces: int
    completed_traces: int
    total_spans: int
    export_handlers: int
    timestamp: str


class TraceDetailResponse(BaseModel):
    """Detailed trace information"""
    trace_id: str
    service_name: str
    total_duration_ms: float
    span_count: int
    root_operation: str
    critical_path_ms: float
    slowest_span: Dict
    error_count: int
    warning_count: int


# ==================== Helper Functions ====================

def _calculate_critical_path(spans: List) -> float:
    """Calculate critical path duration through spans"""
    if not spans:
        return 0.0
    
    # Simple implementation: sum of sequential spans with max nesting depth
    max_duration = 0.0
    for span in spans:
        if span.get('duration_ms', 0) > max_duration:
            max_duration = span['duration_ms']
    
    return max_duration


def _find_slowest_span(spans: List) -> Dict:
    """Find slowest span in list"""
    if not spans:
        return {}
    
    slowest = max(spans, key=lambda s: s.get('duration_ms', 0))
    return {
        "name": slowest.get('name'),
        "duration_ms": slowest.get('duration_ms'),
        "span_id": slowest.get('span_id')
    }


# ==================== API Endpoints ====================

@router.get("/api/tracing/active-traces")
async def get_active_traces() -> Dict[str, List[ActiveTraceResponse]]:
    """
    Get all currently active traces
    
    Returns information about traces that are still being executed.
    """
    try:
        active = tracer.get_active_traces()
        traces = [
            ActiveTraceResponse(**trace_data)
            for trace_data in active.values()
        ]
        
        return {
            "count": len(traces),
            "traces": sorted(traces, key=lambda t: t.duration_ms, reverse=True)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracing/trace/{trace_id}")
async def get_trace(trace_id: str) -> TraceResponse:
    """
    Get complete trace with all spans
    
    Args:
        trace_id: ID of the trace to retrieve
    
    Returns:
        Complete trace information including all spans
    """
    try:
        spans_data = tracer.get_trace_spans(trace_id)
        
        if not spans_data:
            raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
        
        # Calculate totals
        total_duration = sum(s.get('duration_ms', 0) for s in spans_data)
        start_times = [datetime.fromisoformat(s['start_time']) for s in spans_data]
        end_times = [datetime.fromisoformat(s['end_time']) for s in spans_data if s['end_time']]
        
        trace_start = min(start_times) if start_times else datetime.now()
        trace_end = max(end_times) if end_times else None
        
        # Convert spans
        span_responses = [
            SpanResponse(
                trace_id=s['trace_id'],
                span_id=s['span_id'],
                parent_span_id=s['parent_span_id'],
                name=s['name'],
                kind=s['kind'],
                start_time=s['start_time'],
                end_time=s['end_time'],
                duration_ms=round(s['duration_ms'], 2),
                status=s['status'],
                attributes=s['attributes'],
                events=[
                    SpanEventResponse(
                        name=e['name'],
                        timestamp=e['timestamp'],
                        attributes=e['attributes']
                    )
                    for e in s['events']
                ],
                links=[
                    SpanLinkResponse(
                        trace_id=l['trace_id'],
                        span_id=l['span_id'],
                        attributes=l['attributes']
                    )
                    for l in s['links']
                ]
            )
            for s in spans_data
        ]
        
        return TraceResponse(
            trace_id=trace_id,
            span_count=len(span_responses),
            total_duration_ms=round(total_duration, 2),
            start_time=trace_start.isoformat(),
            end_time=trace_end.isoformat() if trace_end else None,
            status="completed" if trace_end else "active",
            spans=span_responses
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracing/span/{trace_id}/{span_id}")
async def get_span(trace_id: str, span_id: str) -> SpanResponse:
    """
    Get specific span information
    
    Args:
        trace_id: Trace ID
        span_id: Span ID
    
    Returns:
        Span details
    """
    try:
        spans_data = tracer.get_trace_spans(trace_id)
        
        span_data = next((s for s in spans_data if s['span_id'] == span_id), None)
        if not span_data:
            raise HTTPException(status_code=404, detail=f"Span {span_id} not found in trace {trace_id}")
        
        return SpanResponse(
            trace_id=span_data['trace_id'],
            span_id=span_data['span_id'],
            parent_span_id=span_data['parent_span_id'],
            name=span_data['name'],
            kind=span_data['kind'],
            start_time=span_data['start_time'],
            end_time=span_data['end_time'],
            duration_ms=round(span_data['duration_ms'], 2),
            status=span_data['status'],
            attributes=span_data['attributes'],
            events=[
                SpanEventResponse(
                    name=e['name'],
                    timestamp=e['timestamp'],
                    attributes=e['attributes']
                )
                for e in span_data['events']
            ],
            links=[
                SpanLinkResponse(
                    trace_id=l['trace_id'],
                    span_id=l['span_id'],
                    attributes=l['attributes']
                )
                for l in span_data['links']
            ]
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracing/statistics")
async def get_tracing_statistics() -> TracerStatsResponse:
    """
    Get tracer statistics
    
    Returns information about tracing system state.
    """
    try:
        stats = tracer.get_statistics()
        
        return TracerStatsResponse(
            active_traces=stats['active_traces'],
            completed_traces=stats['completed_traces'],
            total_spans=stats['total_spans'],
            export_handlers=stats['export_handlers'],
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracing/trace/{trace_id}/details")
async def get_trace_details(trace_id: str) -> TraceDetailResponse:
    """
    Get detailed analysis of a trace
    
    Includes critical path, performance analysis, and error summary.
    """
    try:
        spans_data = tracer.get_trace_spans(trace_id)
        
        if not spans_data:
            raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
        
        # Calculate metrics
        total_duration = sum(s.get('duration_ms', 0) for s in spans_data)
        critical_path = _calculate_critical_path(spans_data)
        slowest = _find_slowest_span(spans_data)
        error_count = sum(1 for s in spans_data if s['status'] == 'ERROR')
        warning_count = sum(1 for s in spans_data if 'warning' in s.get('attributes', {}).get('level', '').lower())
        
        # Get root operation name
        root_spans = [s for s in spans_data if not s.get('parent_span_id')]
        root_op = root_spans[0]['name'] if root_spans else "unknown"
        
        return TraceDetailResponse(
            trace_id=trace_id,
            service_name="rentscout",
            total_duration_ms=round(total_duration, 2),
            span_count=len(spans_data),
            root_operation=root_op,
            critical_path_ms=round(critical_path, 2),
            slowest_span=slowest,
            error_count=error_count,
            warning_count=warning_count
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracing/traces/by-operation/{operation}")
async def get_traces_by_operation(
    operation: str,
    limit: int = Query(10, ge=1, le=100)
) -> Dict:
    """
    Get traces filtered by root operation
    
    Args:
        operation: Operation name to filter by
        limit: Maximum number of traces to return
    
    Returns:
        List of matching traces
    """
    try:
        matching_traces = []
        
        for context in tracer.completed_traces[-1000:]:  # Check recent traces
            spans = context.get_all_spans()
            root_spans = [s for s in spans if not s.parent_span_id]
            
            for root in root_spans:
                if operation.lower() in root.name.lower():
                    total_duration = sum(s.duration_ms for s in spans)
                    matching_traces.append({
                        "trace_id": context.trace_id,
                        "operation": root.name,
                        "span_count": len(spans),
                        "duration_ms": round(total_duration, 2)
                    })
                    break
        
        return {
            "operation": operation,
            "count": len(matching_traces),
            "traces": sorted(matching_traces, key=lambda t: t['duration_ms'], reverse=True)[:limit]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracing/traces/slow")
async def get_slow_traces(
    threshold_ms: float = Query(5000, description="Threshold in milliseconds"),
    limit: int = Query(10, ge=1, le=100)
) -> Dict:
    """
    Get traces that took longer than threshold
    
    Args:
        threshold_ms: Duration threshold in milliseconds
        limit: Maximum number of traces to return
    
    Returns:
        List of slow traces
    """
    try:
        slow_traces = []
        
        for context in tracer.completed_traces[-1000:]:
            spans = context.get_all_spans()
            total_duration = sum(s.duration_ms for s in spans)
            
            if total_duration > threshold_ms:
                root_spans = [s for s in spans if not s.parent_span_id]
                operation = root_spans[0].name if root_spans else "unknown"
                
                slow_traces.append({
                    "trace_id": context.trace_id,
                    "operation": operation,
                    "duration_ms": round(total_duration, 2),
                    "span_count": len(spans)
                })
        
        return {
            "threshold_ms": threshold_ms,
            "count": len(slow_traces),
            "traces": sorted(slow_traces, key=lambda t: t['duration_ms'], reverse=True)[:limit]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracing/traces/errors")
async def get_error_traces(limit: int = Query(10, ge=1, le=100)) -> Dict:
    """
    Get traces that contain errors
    
    Args:
        limit: Maximum number of traces to return
    
    Returns:
        List of traces with errors
    """
    try:
        error_traces = []
        
        for context in tracer.completed_traces[-1000:]:
            spans = context.get_all_spans()
            error_spans = [s for s in spans if s.status.value == 'ERROR']
            
            if error_spans:
                root_spans = [s for s in spans if not s.parent_span_id]
                operation = root_spans[0].name if root_spans else "unknown"
                total_duration = sum(s.duration_ms for s in spans)
                
                error_traces.append({
                    "trace_id": context.trace_id,
                    "operation": operation,
                    "error_count": len(error_spans),
                    "total_spans": len(spans),
                    "duration_ms": round(total_duration, 2),
                    "first_error": error_spans[0].attributes.get('error.message', 'unknown') if error_spans else None
                })
        
        return {
            "count": len(error_traces),
            "traces": sorted(error_traces, key=lambda t: t['duration_ms'], reverse=True)[:limit]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracing/health")
async def tracing_health() -> Dict:
    """
    Check health of distributed tracing system
    
    Returns status and capacity information.
    """
    stats = tracer.get_statistics()
    
    return {
        "status": "healthy",
        "service_name": tracer.service_name,
        "active_traces": stats['active_traces'],
        "completed_traces": stats['completed_traces'],
        "total_spans": stats['total_spans'],
        "export_handlers": stats['export_handlers'],
        "capacity_used_percent": round(
            (stats['active_traces'] / 100) * 100, 2
        ),
        "timestamp": datetime.now().isoformat()
    }
