import logging
import time
from prometheus_client import Counter, Gauge, Histogram
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
    ['method', 'endpoint', 'status_code'],
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


class MetricsCollector:
    """Коллектор метрик для мониторинга производительности."""

    def __init__(self):
        self.start_time = time.time()

    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Запись метрик HTTP запроса."""
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=status_code).inc()
        REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)
        logger.debug(f"Recorded request: {method} {endpoint} {status_code} in {duration:.4f}s")

    def record_parser_call(self, parser_name: str, status: str, duration: float):
        """Запись метрик вызова парсера."""
        PARSER_CALLS.labels(parser_name=parser_name, status=status).inc()
        PARSER_DURATION.labels(parser_name=parser_name).observe(duration)
        logger.debug(f"Recorded parser call: {parser_name} {status} in {duration:.4f}s")

    def start_request(self):
        """Увеличение счетчика активных запросов."""
        ACTIVE_REQUESTS.inc()

    def end_request(self):
        """Уменьшение счетчика активных запросов."""
        ACTIVE_REQUESTS.dec()

    def get_uptime(self) -> float:
        """Получение времени работы приложения."""
        return time.time() - self.start_time


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
