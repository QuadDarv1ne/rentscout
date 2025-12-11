"""
Advanced Prometheus metrics for comprehensive system monitoring.

This module provides enhanced metrics collection for:
- Parser performance (success rate, duration, items parsed)
- Cache efficiency (hit rate, eviction, memory usage)
- Database operations (query time, connection pool status)
- API performance (response time by endpoint, error rates)
- System resources (CPU, memory, active connections)
"""

from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import time
import threading
import psutil
import asyncio

from app.utils.logger import logger


# ============================================================================
# REGISTRY & GLOBAL SETUP
# ============================================================================

class MetricsRegistry:
    """Centralized metrics registry for better organization."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.registry = CollectorRegistry()
            self._initialize_metrics()
            self._initialized = True
    
    def _initialize_metrics(self):
        """Initialize all metrics."""
        # Parser metrics
        self.parser_attempts = Counter(
            'parser_attempts_total',
            'Total parser attempts by source',
            ['source', 'status'],  # status: success, failure, timeout
            registry=self.registry
        )
        
        self.parser_duration = Histogram(
            'parser_duration_seconds',
            'Parser execution duration by source',
            ['source'],
            buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120),
            registry=self.registry
        )
        
        self.items_parsed = Counter(
            'items_parsed_total',
            'Total items parsed by source',
            ['source'],
            registry=self.registry
        )
        
        self.parsing_errors = Counter(
            'parsing_errors_total',
            'Total parsing errors by source and error type',
            ['source', 'error_type'],
            registry=self.registry
        )
        
        # Cache metrics
        self.cache_hits = Counter(
            'cache_hits_total',
            'Total cache hits by level',
            ['level', 'key_pattern'],  # level: l1, l2, redis
            registry=self.registry
        )
        
        self.cache_misses = Counter(
            'cache_misses_total',
            'Total cache misses by level',
            ['level'],
            registry=self.registry
        )
        
        self.cache_hit_ratio = Gauge(
            'cache_hit_ratio',
            'Cache hit ratio (0-1) by level',
            ['level'],
            registry=self.registry
        )
        
        self.cache_memory_usage = Gauge(
            'cache_memory_usage_bytes',
            'Current cache memory usage in bytes by level',
            ['level'],
            registry=self.registry
        )
        
        self.cache_evictions = Counter(
            'cache_evictions_total',
            'Total cache evictions by level and reason',
            ['level', 'reason'],  # reason: lru, ttl, memory
            registry=self.registry
        )
        
        self.cache_operations_duration = Histogram(
            'cache_operations_duration_seconds',
            'Cache operation duration by operation type',
            ['operation', 'level'],  # operation: get, set, delete
            buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05),
            registry=self.registry
        )
        
        # Database metrics
        self.db_queries = Counter(
            'db_queries_total',
            'Total database queries by operation',
            ['operation', 'table'],  # operation: select, insert, update, delete
            registry=self.registry
        )
        
        self.db_query_duration = Histogram(
            'db_query_duration_seconds',
            'Database query duration by operation',
            ['operation', 'table'],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5),
            registry=self.registry
        )
        
        self.db_connection_pool_size = Gauge(
            'db_connection_pool_size',
            'Current database connection pool size',
            registry=self.registry
        )
        
        self.db_connection_active = Gauge(
            'db_connection_active',
            'Number of active database connections',
            registry=self.registry
        )
        
        self.db_errors = Counter(
            'db_errors_total',
            'Total database errors by type',
            ['error_type'],
            registry=self.registry
        )
        
        # API metrics
        self.http_requests = Counter(
            'http_requests_total',
            'Total HTTP requests by endpoint and method',
            ['endpoint', 'method', 'status'],
            registry=self.registry
        )
        
        self.http_request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration by endpoint',
            ['endpoint', 'method'],
            buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10),
            registry=self.registry
        )
        
        self.http_request_size = Summary(
            'http_request_size_bytes',
            'HTTP request size by endpoint',
            ['endpoint'],
            registry=self.registry
        )
        
        self.http_response_size = Summary(
            'http_response_size_bytes',
            'HTTP response size by endpoint',
            ['endpoint'],
            registry=self.registry
        )
        
        # System resource metrics
        self.system_cpu_usage = Gauge(
            'system_cpu_usage_percent',
            'System CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_usage = Gauge(
            'system_memory_usage_bytes',
            'System memory usage in bytes',
            registry=self.registry
        )
        
        self.system_memory_percent = Gauge(
            'system_memory_percent',
            'System memory usage percentage',
            registry=self.registry
        )
        
        self.process_memory_usage = Gauge(
            'process_memory_usage_bytes',
            'Process memory usage in bytes',
            registry=self.registry
        )
        
        self.active_connections = Gauge(
            'active_connections',
            'Number of active connections by type',
            ['connection_type'],  # http, db, redis
            registry=self.registry
        )
        
        # Application-level metrics
        self.duplicate_detection = Counter(
            'duplicate_detection_total',
            'Total duplicates detected and removed',
            ['source'],
            registry=self.registry
        )
        
        self.data_quality_score = Gauge(
            'data_quality_score',
            'Overall data quality score (0-100)',
            registry=self.registry
        )
        
        self.indexing_operations = Counter(
            'indexing_operations_total',
            'Total indexing operations by status',
            ['status'],  # success, failure
            registry=self.registry
        )
        
        self.indexing_duration = Histogram(
            'indexing_duration_seconds',
            'Indexing operation duration',
            buckets=(0.1, 0.5, 1, 5, 10, 30, 60),
            registry=self.registry
        )


# Global instance
metrics_registry = MetricsRegistry()


# ============================================================================
# METRIC COLLECTORS & REPORTERS
# ============================================================================

@dataclass
class ParserMetrics:
    """Container for parser performance metrics."""
    source: str
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    total_items: int = 0
    total_duration: float = 0.0
    errors: Dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_success(self, items: int, duration: float):
        """Record successful parse."""
        self.success_count += 1
        self.total_items += items
        self.total_duration += duration
    
    def add_failure(self, error_type: str, duration: float):
        """Record failed parse."""
        self.failure_count += 1
        self.total_duration += duration
        self.errors[error_type] = self.errors.get(error_type, 0) + 1
    
    def add_timeout(self, duration: float):
        """Record timeout."""
        self.timeout_count += 1
        self.total_duration += duration
        self.add_failure('timeout', 0)
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        total = self.success_count + self.failure_count + self.timeout_count
        if total == 0:
            return 0.0
        return (self.success_count / total) * 100
    
    def get_avg_duration(self) -> float:
        """Calculate average duration."""
        total = self.success_count + self.failure_count + self.timeout_count
        if total == 0:
            return 0.0
        return self.total_duration / total
    
    def get_avg_items_per_parse(self) -> float:
        """Calculate average items per successful parse."""
        if self.success_count == 0:
            return 0.0
        return self.total_items / self.success_count


@dataclass
class CacheMetrics:
    """Container for cache performance metrics."""
    level: str  # l1, l2, redis
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_bytes: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_hit(self):
        """Record cache hit."""
        self.hits += 1
    
    def add_miss(self):
        """Record cache miss."""
        self.misses += 1
    
    def add_eviction(self):
        """Record eviction."""
        self.evictions += 1
    
    def get_hit_ratio(self) -> float:
        """Calculate hit ratio (0-1)."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
    
    def get_hit_rate_percent(self) -> float:
        """Calculate hit rate percentage."""
        return self.get_hit_ratio() * 100


@dataclass
class APIMetrics:
    """Container for API performance metrics."""
    endpoint: str
    method: str = "GET"
    requests_total: int = 0
    errors_total: int = 0
    total_duration: float = 0.0
    status_codes: Dict[int, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_request(self, duration: float, status_code: int):
        """Record API request."""
        self.requests_total += 1
        self.total_duration += duration
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
        
        if status_code >= 400:
            self.errors_total += 1
    
    def get_avg_duration(self) -> float:
        """Calculate average request duration."""
        if self.requests_total == 0:
            return 0.0
        return self.total_duration / self.requests_total
    
    def get_error_rate(self) -> float:
        """Calculate error rate percentage."""
        if self.requests_total == 0:
            return 0.0
        return (self.errors_total / self.requests_total) * 100
    
    def get_most_common_status(self) -> int:
        """Get most common status code."""
        if not self.status_codes:
            return 0
        return max(self.status_codes, key=self.status_codes.get)


class SystemMetricsCollector:
    """Collect system-level metrics (CPU, memory, connections)."""
    
    @staticmethod
    def update_system_metrics():
        """Update system resource metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            metrics_registry.system_cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            metrics_registry.system_memory_usage.set(memory.used)
            metrics_registry.system_memory_percent.set(memory.percent)
            
            # Process memory
            process = psutil.Process()
            process_memory = process.memory_info().rss
            metrics_registry.process_memory_usage.set(process_memory)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    @staticmethod
    def start_background_collection(interval: int = 60):
        """Start background collection of system metrics."""
        def collect_periodically():
            while True:
                try:
                    SystemMetricsCollector.update_system_metrics()
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"System metrics collection error: {e}")
                    time.sleep(interval)
        
        thread = threading.Thread(target=collect_periodically, daemon=True)
        thread.start()
        logger.info("System metrics collector started")


class MetricsReporter:
    """Generate metrics reports for monitoring and analysis."""
    
    def __init__(self):
        self.parser_metrics: Dict[str, ParserMetrics] = {}
        self.cache_metrics: Dict[str, CacheMetrics] = {}
        self.api_metrics: Dict[tuple, APIMetrics] = {}
    
    def record_parser_success(
        self,
        source: str,
        items: int,
        duration: float
    ):
        """Record successful parse."""
        if source not in self.parser_metrics:
            self.parser_metrics[source] = ParserMetrics(source=source)
        
        self.parser_metrics[source].add_success(items, duration)
        metrics_registry.parser_attempts.labels(source=source, status='success').inc()
        metrics_registry.parser_duration.labels(source=source).observe(duration)
        metrics_registry.items_parsed.labels(source=source).inc(items)
    
    def record_parser_failure(
        self,
        source: str,
        error_type: str,
        duration: float
    ):
        """Record failed parse."""
        if source not in self.parser_metrics:
            self.parser_metrics[source] = ParserMetrics(source=source)
        
        self.parser_metrics[source].add_failure(error_type, duration)
        metrics_registry.parser_attempts.labels(source=source, status='failure').inc()
        metrics_registry.parsing_errors.labels(source=source, error_type=error_type).inc()
        metrics_registry.parser_duration.labels(source=source).observe(duration)
    
    def record_cache_hit(
        self,
        level: str,
        key_pattern: str = "default"
    ):
        """Record cache hit."""
        if level not in self.cache_metrics:
            self.cache_metrics[level] = CacheMetrics(level=level)
        
        self.cache_metrics[level].add_hit()
        metrics_registry.cache_hits.labels(level=level, key_pattern=key_pattern).inc()
        self._update_cache_hit_ratio(level)
    
    def record_cache_miss(self, level: str):
        """Record cache miss."""
        if level not in self.cache_metrics:
            self.cache_metrics[level] = CacheMetrics(level=level)
        
        self.cache_metrics[level].add_miss()
        metrics_registry.cache_misses.labels(level=level).inc()
        self._update_cache_hit_ratio(level)
    
    def record_cache_eviction(
        self,
        level: str,
        reason: str = "lru"
    ):
        """Record cache eviction."""
        if level not in self.cache_metrics:
            self.cache_metrics[level] = CacheMetrics(level=level)
        
        self.cache_metrics[level].add_eviction()
        metrics_registry.cache_evictions.labels(level=level, reason=reason).inc()
    
    def record_cache_operation(
        self,
        operation: str,
        level: str,
        duration: float
    ):
        """Record cache operation duration."""
        metrics_registry.cache_operations_duration.labels(
            operation=operation,
            level=level
        ).observe(duration)
    
    def record_db_query(
        self,
        operation: str,
        table: str,
        duration: float,
        success: bool = True
    ):
        """Record database query."""
        metrics_registry.db_queries.labels(operation=operation, table=table).inc()
        metrics_registry.db_query_duration.labels(operation=operation, table=table).observe(duration)
        
        if not success:
            metrics_registry.db_errors.labels(error_type='query_failed').inc()
    
    def record_api_request(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        duration: float,
        request_size: int = 0,
        response_size: int = 0
    ):
        """Record API request."""
        key = (endpoint, method)
        if key not in self.api_metrics:
            self.api_metrics[key] = APIMetrics(endpoint=endpoint, method=method)
        
        self.api_metrics[key].add_request(duration, status_code)
        metrics_registry.http_requests.labels(endpoint=endpoint, method=method, status=status_code).inc()
        metrics_registry.http_request_duration.labels(endpoint=endpoint, method=method).observe(duration)
        
        if request_size > 0:
            metrics_registry.http_request_size.labels(endpoint=endpoint).observe(request_size)
        if response_size > 0:
            metrics_registry.http_response_size.labels(endpoint=endpoint).observe(response_size)
    
    def update_db_pool_status(self, pool_size: int, active: int):
        """Update database connection pool status."""
        metrics_registry.db_connection_pool_size.set(pool_size)
        metrics_registry.db_connection_active.set(active)
    
    def update_active_connections(self, connection_type: str, count: int):
        """Update active connections count."""
        metrics_registry.active_connections.labels(connection_type=connection_type).set(count)
    
    def update_cache_memory(self, level: str, bytes_used: int):
        """Update cache memory usage."""
        if level in self.cache_metrics:
            self.cache_metrics[level].memory_bytes = bytes_used
        metrics_registry.cache_memory_usage.labels(level=level).set(bytes_used)
    
    def record_duplicate_detection(self, source: str, count: int):
        """Record duplicates detected."""
        metrics_registry.duplicate_detection.labels(source=source).inc(count)
    
    def update_data_quality_score(self, score: float):
        """Update overall data quality score (0-100)."""
        metrics_registry.data_quality_score.set(min(100, max(0, score)))
    
    def record_indexing_operation(self, success: bool, duration: float):
        """Record indexing operation."""
        status = "success" if success else "failure"
        metrics_registry.indexing_operations.labels(status=status).inc()
        metrics_registry.indexing_duration.observe(duration)
    
    def _update_cache_hit_ratio(self, level: str):
        """Update cache hit ratio gauge."""
        if level in self.cache_metrics:
            ratio = self.cache_metrics[level].get_hit_ratio()
            metrics_registry.cache_hit_ratio.labels(level=level).set(ratio)
    
    def get_summary_report(self) -> Dict[str, Any]:
        """Generate comprehensive metrics summary."""
        parser_summary = {}
        for source, metrics in self.parser_metrics.items():
            parser_summary[source] = {
                'success_rate_percent': round(metrics.get_success_rate(), 2),
                'avg_duration_seconds': round(metrics.get_avg_duration(), 3),
                'total_items': metrics.total_items,
                'success_count': metrics.success_count,
                'failure_count': metrics.failure_count,
                'timeout_count': metrics.timeout_count,
                'avg_items_per_parse': round(metrics.get_avg_items_per_parse(), 2),
            }
        
        cache_summary = {}
        for level, metrics in self.cache_metrics.items():
            cache_summary[level] = {
                'hit_rate_percent': round(metrics.get_hit_rate_percent(), 2),
                'hits': metrics.hits,
                'misses': metrics.misses,
                'evictions': metrics.evictions,
                'memory_bytes': metrics.memory_bytes,
            }
        
        api_summary = {}
        for (endpoint, method), metrics in self.api_metrics.items():
            key = f"{method} {endpoint}"
            api_summary[key] = {
                'requests_total': metrics.requests_total,
                'errors_total': metrics.errors_total,
                'error_rate_percent': round(metrics.get_error_rate(), 2),
                'avg_duration_seconds': round(metrics.get_avg_duration(), 3),
                'most_common_status': metrics.get_most_common_status(),
            }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'parsers': parser_summary,
            'cache': cache_summary,
            'api': api_summary,
        }


# Global reporter instance
metrics_reporter = MetricsReporter()


# ============================================================================
# CONTEXT MANAGERS FOR MONITORING
# ============================================================================

class MonitorParserExecution:
    """Context manager for monitoring parser execution."""
    
    def __init__(self, source: str):
        self.source = source
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        
        if exc_type is None:
            metrics_reporter.record_parser_success(self.source, 0, duration)
        else:
            error_type = exc_type.__name__
            metrics_reporter.record_parser_failure(self.source, error_type, duration)
        
        return False


class MonitorCacheOperation:
    """Context manager for monitoring cache operations."""
    
    def __init__(self, operation: str, level: str):
        self.operation = operation
        self.level = level
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        metrics_reporter.record_cache_operation(self.operation, self.level, duration)
        return False


class MonitorDatabaseQuery:
    """Context manager for monitoring database queries."""
    
    def __init__(self, operation: str, table: str):
        self.operation = operation
        self.table = table
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.perf_counter() - self.start_time
        success = exc_type is None
        metrics_reporter.record_db_query(self.operation, self.table, duration, success)
        return False
