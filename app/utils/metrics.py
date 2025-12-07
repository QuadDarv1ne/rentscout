import logging
import time
from prometheus_client import Counter, Gauge, Histogram, Summary
from typing import Any, Dict

from app.utils.logger import logger

# Определение метрик Prometheus
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)
)

REQUEST_ERRORS = Counter(
    'http_requests_errors_total',
    'Total HTTP requests ending with 5xx',
    ['method', 'endpoint']
)

ACTIVE_REQUESTS = Gauge('http_active_requests', 'Number of active HTTP requests')

PARSER_CALLS = Counter('parser_calls_total', 'Total parser calls', ['parser_name', 'status'])

PARSER_DURATION = Histogram('parser_duration_seconds', 'Parser execution duration in seconds', ['parser_name'])

PARSER_ERRORS = Counter('parser_errors_total', 'Total parser errors', ['parser_name', 'error_type'])

# Database metrics
DB_QUERIES = Counter('db_queries_total', 'Total database queries', ['query_type', 'table'])

DB_QUERY_DURATION = Histogram('db_query_duration_seconds', 'Database query duration in seconds', ['query_type', 'table'])

DB_CONNECTIONS_ACTIVE = Gauge('db_connections_active', 'Number of active database connections')

# Cache metrics
CACHE_HITS = Counter('cache_hits_total', 'Total cache hits')

CACHE_MISSES = Counter('cache_misses_total', 'Total cache misses')

CACHE_ERRORS = Counter('cache_errors_total', 'Total cache errors')

CACHE_HIT_RATE = Gauge('cache_hit_rate', 'Cache hit rate')

# Task metrics
TASKS_PROCESSED = Counter('tasks_processed_total', 'Total processed tasks', ['task_type', 'status'])

TASKS_QUEUED = Gauge('tasks_queued', 'Number of tasks currently queued', ['task_type'])

# Rate limiting metrics
RATE_LIMIT_EXCEEDED = Counter('rate_limit_exceeded_total', 'Total rate limit violations', ['client_ip'])

RATE_LIMIT_CURRENT = Gauge('rate_limit_current', 'Current rate limit counter', ['client_ip'])

# Application metrics
APPLICATION_UPTIME = Gauge('application_uptime_seconds', 'Application uptime in seconds')

MEMORY_USAGE = Gauge('memory_usage_bytes', 'Application memory usage in bytes')

PROPERTIES_PROCESSED = Counter('properties_processed_total', 'Total properties processed', ['source', 'operation'])

PROPERTIES_SAVED = Counter('properties_saved_total', 'Total properties saved to database')

PROPERTIES_DUPLICATES = Counter('properties_duplicates_total', 'Total duplicate properties detected')


class MetricsCollector:
    """Коллектор метрик для мониторинга производительности."""

    def __init__(self):
        self.start_time = time.time()

    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Запись метрик HTTP запроса."""
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
        logger.debug(f"Recorded request: {method} {endpoint} {status_code} in {duration:.4f}s")

    def record_parser_call(self, parser_name: str, status: str, duration: float, error_type: str = None):
        """Запись метрик вызова парсера."""
        PARSER_CALLS.labels(parser_name=parser_name, status=status).inc()
        PARSER_DURATION.labels(parser_name=parser_name).observe(duration)
        
        if status == "error" and error_type:
            PARSER_ERRORS.labels(parser_name=parser_name, error_type=error_type).inc()
        
        logger.debug(f"Recorded parser call: {parser_name} {status} in {duration:.4f}s")

    def record_db_query(self, query_type: str, table: str, duration: float):
        """Запись метрик базы данных."""
        DB_QUERIES.labels(query_type=query_type, table=table).inc()
        DB_QUERY_DURATION.labels(query_type=query_type, table=table).observe(duration)
        logger.debug(f"Recorded DB query: {query_type} on {table} in {duration:.4f}s")

    def record_cache_hit(self):
        """Запись метрики кеш хита."""
        CACHE_HITS.inc()
        self._update_cache_hit_rate()

    def record_cache_miss(self):
        """Запись метрики кеш мисса."""
        CACHE_MISSES.inc()
        self._update_cache_hit_rate()

    def record_cache_error(self):
        """Запись метрики ошибки кеша."""
        CACHE_ERRORS.inc()

    def _update_cache_hit_rate(self):
        """Обновление метрики коэффициента попаданий в кеш."""
        hits = CACHE_HITS._value.get()
        misses = CACHE_MISSES._value.get()
        total = hits + misses
        if total > 0:
            CACHE_HIT_RATE.set(hits / total)

    def record_task_processed(self, task_type: str, status: str):
        """Запись метрики обработанной задачи."""
        TASKS_PROCESSED.labels(task_type=task_type, status=status).inc()

    def record_task_queued(self, task_type: str, count: int):
        """Запись метрики задач в очереди."""
        TASKS_QUEUED.labels(task_type=task_type).set(count)

    def record_rate_limit_exceeded(self, client_ip: str):
        """Запись метрики превышения лимита."""
        RATE_LIMIT_EXCEEDED.labels(client_ip=client_ip).inc()

    def record_rate_limit_current(self, client_ip: str, count: int):
        """Запись текущего счетчика рейт-лимита."""
        RATE_LIMIT_CURRENT.labels(client_ip=client_ip).set(count)

    def record_property_processed(self, source: str, operation: str):
        """Запись метрики обработанного объявления."""
        PROPERTIES_PROCESSED.labels(source=source, operation=operation).inc()

    def record_property_saved(self):
        """Запись метрики сохраненного объявления."""
        PROPERTIES_SAVED.inc()

    def record_duplicate_property(self):
        """Запись метрики дубликата объявления."""
        PROPERTIES_DUPLICATES.inc()

    def start_request(self):
        """Увеличение счетчика активных запросов."""
        ACTIVE_REQUESTS.inc()

    def end_request(self):
        """Уменьшение счетчика активных запросов."""
        ACTIVE_REQUESTS.dec()

    def get_uptime(self) -> float:
        """Получение времени работы приложения."""
        uptime = time.time() - self.start_time
        APPLICATION_UPTIME.set(uptime)
        return uptime

    def update_memory_usage(self, bytes_used: int):
        """Обновление метрики использования памяти."""
        MEMORY_USAGE.set(bytes_used)


# Глобальный экземпляр коллектора метрик
metrics_collector = MetricsCollector()


class MetricsMiddleware:
    """Middleware для автоматического сбора метрик HTTP запросов."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Запись начала запроса
        start_time = time.time()
        method = scope["method"]
        endpoint = scope["path"]

        # Увеличение счетчика активных запросов
        metrics_collector.start_request()

        # Оборачиваем send для перехвата статуса ответа
        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                duration = time.time() - start_time

                # Запись метрик
                metrics_collector.record_request(method, endpoint, status_code, duration)

                if 500 <= status_code <= 599:
                    REQUEST_ERRORS.labels(method=method, endpoint=endpoint).inc()

            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            # Уменьшение счетчика активных запросов
            metrics_collector.end_request()