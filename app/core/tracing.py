"""
OpenTelemetry Distributed Tracing for RentScout v2.2.0

Provides comprehensive distributed tracing across all services:
- Parser execution tracing
- Database query tracing
- API request tracing
- Cache operation tracing
- Error path tracing
- Performance metrics export
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from contextlib import contextmanager
import uuid

logger = logging.getLogger(__name__)


class SpanKind(Enum):
    """Type of span for OpenTelemetry"""
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class SpanStatus(Enum):
    """Status of a span"""
    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


@dataclass
class SpanEvent:
    """Event within a span"""
    name: str
    timestamp: datetime = field(default_factory=datetime.now)
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SpanLink:
    """Link to another span"""
    trace_id: str
    span_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """OpenTelemetry-compatible span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    kind: SpanKind
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    links: List[SpanLink] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> float:
        """Duration of span in milliseconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return (datetime.now() - self.start_time).total_seconds() * 1000
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add event to span"""
        self.events.append(SpanEvent(name=name, attributes=attributes or {}))
    
    def add_attribute(self, key: str, value: Any):
        """Add attribute to span"""
        self.attributes[key] = value
    
    def add_link(self, trace_id: str, span_id: str, attributes: Optional[Dict[str, Any]] = None):
        """Add link to another span"""
        self.links.append(SpanLink(trace_id=trace_id, span_id=span_id, attributes=attributes or {}))
    
    def set_error(self, error_type: str, error_message: str):
        """Mark span as error"""
        self.status = SpanStatus.ERROR
        self.add_attribute("error.type", error_type)
        self.add_attribute("error.message", error_message)
        self.add_event("exception", {
            "exception.type": error_type,
            "exception.message": error_message
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary"""
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": [
                {
                    "name": e.name,
                    "timestamp": e.timestamp.isoformat(),
                    "attributes": e.attributes
                }
                for e in self.events
            ],
            "links": [
                {
                    "trace_id": l.trace_id,
                    "span_id": l.span_id,
                    "attributes": l.attributes
                }
                for l in self.links
            ]
        }


class TraceContext:
    """Context for distributed tracing"""
    
    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.current_span_id: Optional[str] = None
        self.spans: Dict[str, Span] = {}
        self.span_stack: List[str] = []  # Stack of active span IDs
    
    def get_current_span(self) -> Optional[Span]:
        """Get current active span"""
        if self.current_span_id:
            return self.spans.get(self.current_span_id)
        return None
    
    def create_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Span:
        """Create new span"""
        span_id = str(uuid.uuid4())
        parent_span_id = self.current_span_id
        
        span = Span(
            trace_id=self.trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            attributes=attributes or {}
        )
        
        self.spans[span_id] = span
        return span
    
    def push_span(self, span: Span):
        """Push span to active stack"""
        self.span_stack.append(span.span_id)
        self.current_span_id = span.span_id
    
    def pop_span(self):
        """Pop span from active stack"""
        if self.span_stack:
            self.span_stack.pop()
            self.current_span_id = self.span_stack[-1] if self.span_stack else None
    
    def get_all_spans(self) -> List[Span]:
        """Get all spans in trace"""
        return list(self.spans.values())


class Tracer:
    """OpenTelemetry-compatible tracer"""
    
    def __init__(self, service_name: str = "rentscout"):
        self.service_name = service_name
        self.trace_contexts: Dict[str, TraceContext] = {}
        self.completed_traces: List[TraceContext] = []
        self.max_completed_traces = 1000
        self.export_handlers: List[callable] = []
    
    def get_or_create_context(self, trace_id: Optional[str] = None) -> TraceContext:
        """Get or create trace context"""
        if trace_id and trace_id in self.trace_contexts:
            return self.trace_contexts[trace_id]
        
        context = TraceContext(trace_id)
        self.trace_contexts[context.trace_id] = context
        return context
    
    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Span:
        """Start new span"""
        context = self.get_or_create_context(trace_id)
        span = context.create_span(name, kind, attributes)
        context.push_span(span)
        return span
    
    def end_span(self, span: Span):
        """End span and export if root"""
        span.end_time = datetime.now()
        span.status = SpanStatus.OK
        
        # Get context and pop span
        context = self.trace_contexts.get(span.trace_id)
        if context:
            context.pop_span()
            
            # If this was root span, finalize trace
            if not context.span_stack:
                self._finalize_trace(context)
    
    def _finalize_trace(self, context: TraceContext):
        """Finalize and export completed trace"""
        # Export trace
        self._export_trace(context)
        
        # Store completed trace
        self.completed_traces.append(context)
        if len(self.completed_traces) > self.max_completed_traces:
            self.completed_traces = self.completed_traces[-self.max_completed_traces:]
        
        # Clean up context
        if context.trace_id in self.trace_contexts:
            del self.trace_contexts[context.trace_id]
    
    def _export_trace(self, context: TraceContext):
        """Export trace to registered handlers"""
        for handler in self.export_handlers:
            try:
                handler(context)
            except Exception as e:
                logger.error(f"Error exporting trace: {e}")
    
    def add_export_handler(self, handler: callable):
        """Add handler for trace export"""
        self.export_handlers.append(handler)
    
    def get_active_traces(self) -> Dict[str, Dict]:
        """Get all active traces"""
        return {
            trace_id: {
                "trace_id": trace_id,
                "span_count": len(context.spans),
                "active_spans": len(context.span_stack),
                "duration_ms": (datetime.now() - context.get_all_spans()[0].start_time).total_seconds() * 1000
                if context.get_all_spans() else 0
            }
            for trace_id, context in self.trace_contexts.items()
        }
    
    def get_trace_spans(self, trace_id: str) -> List[Dict]:
        """Get all spans for a trace"""
        context = self.trace_contexts.get(trace_id)
        if not context:
            # Check completed traces
            for ctx in self.completed_traces:
                if ctx.trace_id == trace_id:
                    return [span.to_dict() for span in ctx.get_all_spans()]
            return []
        
        return [span.to_dict() for span in context.get_all_spans()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get tracer statistics"""
        return {
            "active_traces": len(self.trace_contexts),
            "completed_traces": len(self.completed_traces),
            "total_spans": sum(len(ctx.spans) for ctx in self.trace_contexts.values()) +
                          sum(len(ctx.spans) for ctx in self.completed_traces),
            "export_handlers": len(self.export_handlers),
        }


class SpanContextManager:
    """Context manager for spans"""
    
    def __init__(self, tracer: Tracer, span: Span):
        self.tracer = tracer
        self.span = span
    
    def __enter__(self):
        return self.span
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.span.set_error(
                error_type=exc_type.__name__,
                error_message=str(exc_val)
            )
        self.tracer.end_span(self.span)


class ParserSpanContext:
    """Context for parser spans"""
    
    def __init__(self, tracer: Tracer, parser_name: str, source_url: str):
        self.tracer = tracer
        self.parser_name = parser_name
        self.source_url = source_url
        self.span = tracer.start_span(
            name=f"parse_{parser_name}",
            kind=SpanKind.INTERNAL,
            attributes={
                "parser.name": parser_name,
                "parser.source": source_url,
            }
        )
    
    def add_fetch_event(self, url: str, status_code: int, duration_ms: float):
        """Add fetch event to parser span"""
        self.span.add_event("fetch", {
            "http.url": url,
            "http.status_code": status_code,
            "http.duration_ms": duration_ms
        })
    
    def add_parse_event(self, items_count: int, duration_ms: float):
        """Add parse event to parser span"""
        self.span.add_event("parse", {
            "parser.items_count": items_count,
            "parser.duration_ms": duration_ms
        })
    
    def add_validation_event(self, items_valid: int, items_invalid: int):
        """Add validation event to parser span"""
        self.span.add_event("validate", {
            "validation.valid_items": items_valid,
            "validation.invalid_items": items_invalid
        })
    
    def end(self):
        """End parser span"""
        self.tracer.end_span(self.span)


class DatabaseSpanContext:
    """Context for database query spans"""
    
    def __init__(self, tracer: Tracer, query_type: str, table: str):
        self.tracer = tracer
        self.span = tracer.start_span(
            name=f"db_{query_type}_{table}",
            kind=SpanKind.CLIENT,
            attributes={
                "db.type": "postgresql",
                "db.operation": query_type,
                "db.table": table
            }
        )
    
    def add_rows_affected(self, count: int):
        """Record number of rows affected"""
        self.span.add_attribute("db.rows_affected", count)
    
    def end(self):
        """End database span"""
        self.tracer.end_span(self.span)


class APISpanContext:
    """Context for API request spans"""
    
    def __init__(self, tracer: Tracer, method: str, path: str):
        self.tracer = tracer
        self.span = tracer.start_span(
            name=f"api_{method}_{path}",
            kind=SpanKind.SERVER,
            attributes={
                "http.method": method,
                "http.route": path,
            }
        )
    
    def set_response(self, status_code: int, response_time_ms: float):
        """Set API response details"""
        self.span.add_attribute("http.status_code", status_code)
        self.span.add_attribute("http.response_time_ms", response_time_ms)
    
    def end(self):
        """End API span"""
        self.tracer.end_span(self.span)


# Global tracer instance
tracer = Tracer(service_name="rentscout")


def export_to_prometheus(context: TraceContext):
    """Export trace to Prometheus format"""
    try:
        spans = context.get_all_spans()
        for span in spans:
            logger.info(f"Trace {context.trace_id}: {span.name} ({span.duration_ms:.2f}ms)")
    except Exception as e:
        logger.error(f"Error exporting to Prometheus: {e}")


def export_to_jaeger(context: TraceContext):
    """Export trace to Jaeger format"""
    try:
        # Would integrate with actual Jaeger client in production
        spans_data = [span.to_dict() for span in context.get_all_spans()]
        logger.debug(f"Would export {len(spans_data)} spans to Jaeger")
    except Exception as e:
        logger.error(f"Error exporting to Jaeger: {e}")


# Register export handlers
tracer.add_export_handler(export_to_prometheus)
# tracer.add_export_handler(export_to_jaeger)  # Enable in production with Jaeger


@contextmanager
def trace_parser_execution(parser_name: str, source_url: str):
    """Context manager for parser tracing"""
    span_context = ParserSpanContext(tracer, parser_name, source_url)
    try:
        yield span_context
    finally:
        span_context.end()


@contextmanager
def trace_database_query(query_type: str, table: str):
    """Context manager for database query tracing"""
    span_context = DatabaseSpanContext(tracer, query_type, table)
    try:
        yield span_context
    finally:
        span_context.end()


@contextmanager
def trace_api_request(method: str, path: str):
    """Context manager for API request tracing"""
    start_time = time.time()
    span_context = APISpanContext(tracer, method, path)
    try:
        yield span_context
    finally:
        duration_ms = (time.time() - start_time) * 1000
        span_context.span.add_attribute("http.response_time_ms", duration_ms)
        span_context.end()


def create_child_span(parent_trace_id: str, name: str, kind: SpanKind = SpanKind.INTERNAL) -> Span:
    """Create child span within existing trace"""
    return tracer.start_span(name, parent_trace_id, kind)
