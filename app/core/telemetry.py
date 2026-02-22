"""
OpenTelemetry tracing для распределенной трассировки.

Поддерживает:
- Автоматическое инструментирование FastAPI
- Трассировка HTTP запросов
- Трассировка SQL запросов
- Трассировка Redis операций
- Трассировка парсеров
- Экспорт в Jaeger/Zipkin/OTLP

Использование:
    from app.core.telemetry import setup_telemetry
    
    # В main.py
    setup_telemetry(app, service_name="rentscout")
"""

import os
import time
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager
from functools import wraps
import logging

from app.utils.logger import logger

# Пытаемся импортировать OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.trace import Status, StatusCode
    
    # SpanKind может не быть доступен если OTEL не установлен
    try:
        from opentelemetry.trace import SpanKind
    except ImportError:
        SpanKind = None
    
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    SpanKind = None
    logger.warning("OpenTelemetry not installed. Install with: pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-jaeger opentelemetry-instrumentation-fastapi")


class TelemetryConfig:
    """Конфигурация телеметрии."""
    
    def __init__(
        self,
        service_name: str = "rentscout",
        service_version: str = "1.0.0",
        exporter: str = "console",  # console, jaeger, otlp
        jaeger_endpoint: str = "http://localhost:14268/api/traces",
        otlp_endpoint: str = "localhost:4317",
        sample_rate: float = 1.0,
        enabled: bool = True,
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.exporter = exporter
        self.jaeger_endpoint = jaeger_endpoint
        self.otlp_endpoint = otlp_endpoint
        self.sample_rate = sample_rate
        self.enabled = enabled and OTEL_AVAILABLE


class Telemetry:
    """
    Менеджер телеметрии для распределенной трассировки.
    """
    
    _instance: Optional["Telemetry"] = None
    
    def __new__(cls, *args, **kwargs) -> "Telemetry":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config: Optional[TelemetryConfig] = None):
        """Инициализация телеметрии."""
        if hasattr(self, '_initialized'):
            return
            
        self.config = config or TelemetryConfig()
        self.tracer_provider = None
        self.tracer = None
        self._initialized = False
        
        if self.config.enabled:
            self._setup()
    
    def _setup(self) -> None:
        """Настройка OpenTelemetry."""
        if not OTEL_AVAILABLE:
            logger.warning("OpenTelemetry not available, tracing disabled")
            return
        
        # Создаем resource с информацией о сервисе
        resource = Resource.create({
            SERVICE_NAME: self.config.service_name,
            SERVICE_VERSION: self.config.service_version,
        })
        
        # Создаем tracer provider
        self.tracer_provider = TracerProvider(
            resource=resource,
            sampler=None,  # Use default sampler
        )
        
        # Настраиваем экспортер
        exporter = self._create_exporter()
        if exporter:
            span_processor = BatchSpanProcessor(exporter)
            self.tracer_provider.add_span_processor(span_processor)
        
        # Устанавливаем глобальный tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        
        # Получаем tracer
        self.tracer = trace.get_tracer(self.config.service_name)
        
        self._initialized = True
        logger.info(f"✅ OpenTelemetry tracing initialized (exporter: {self.config.exporter})")
    
    def _create_exporter(self):
        """Создает экспортер спанов."""
        if self.config.exporter == "console":
            return ConsoleSpanExporter()
        
        elif self.config.exporter == "jaeger":
            return JaegerExporter(
                collector_endpoint=self.config.jaeger_endpoint,
            )
        
        elif self.config.exporter == "otlp":
            return OTLPSpanExporter(
                endpoint=self.config.otlp_endpoint,
                insecure=True,
            )
        
        else:
            logger.warning(f"Unknown exporter: {self.config.exporter}, using console")
            return ConsoleSpanExporter()
    
    def instrument_fastapi(self, app) -> None:
        """Инструментирование FastAPI приложения."""
        if not OTEL_AVAILABLE or not self._initialized:
            return
        
        try:
            FastAPIInstrumentor.instrument_app(
                app,
                tracer_provider=self.tracer_provider,
            )
            logger.info("✅ FastAPI instrumented")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}")
    
    def instrument_httpx(self) -> None:
        """Инструментирование HTTPX клиента."""
        if not OTEL_AVAILABLE or not self._initialized:
            return
        
        try:
            HTTPXClientInstrumentor().instrument(tracer_provider=self.tracer_provider)
            logger.info("✅ HTTPX instrumented")
        except Exception as e:
            logger.error(f"Failed to instrument HTTPX: {e}")
    
    def instrument_sqlalchemy(self, engine) -> None:
        """Инструментирование SQLAlchemy."""
        if not OTEL_AVAILABLE or not self._initialized:
            return
        
        try:
            SQLAlchemyInstrumentor().instrument(
                engine=engine,
                tracer_provider=self.tracer_provider,
            )
            logger.info("✅ SQLAlchemy instrumented")
        except Exception as e:
            logger.error(f"Failed to instrument SQLAlchemy: {e}")
    
    def instrument_redis(self, redis_client) -> None:
        """Инструментирование Redis."""
        if not OTEL_AVAILABLE or not self._initialized:
            return
        
        try:
            RedisInstrumentor().instrument(
                redis_client,
                tracer_provider=self.tracer_provider,
            )
            logger.info("✅ Redis instrumented")
        except Exception as e:
            logger.error(f"Failed to instrument Redis: {e}")
    
    @contextmanager
    def start_span(self, name: str, kind=None, attributes: Optional[Dict[str, Any]] = None):
        """
        Контекстный менеджер для создания спана.
        
        Args:
            name: Имя спана
            kind: Тип спана
            attributes: Атрибуты спана
        
        Example:
            with telemetry.start_span("process_data") as span:
                # Do work
                span.set_attribute("data.size", 100)
        """
        if not self._initialized or not self.tracer:
            yield None
            return
        
        # SpanKind может быть None если OTEL не установлен
        if kind is None and SpanKind is not None:
            kind = SpanKind.INTERNAL
        
        with self.tracer.start_as_current_span(name, kind=kind) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            yield span
    
    def trace(self, name: Optional[str] = None):
        """
        Декоратор для трассировки функций.
        
        Args:
            name: Имя спана (по умолчанию имя функции)
        
        Example:
            @telemetry.trace("custom_name")
            async def my_function():
                ...
        """
        def decorator(func: Callable):
            span_name = name or func.__name__
            
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not self._initialized:
                    return await func(*args, **kwargs)
                
                with self.start_span(span_name) as span:
                    try:
                        result = await func(*args, **kwargs)
                        if span:
                            span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        if span:
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                            span.record_exception(e)
                        raise
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                if not self._initialized:
                    return func(*args, **kwargs)
                
                with self.start_span(span_name) as span:
                    try:
                        result = func(*args, **kwargs)
                        if span:
                            span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        if span:
                            span.set_status(Status(StatusCode.ERROR, str(e)))
                            span.record_exception(e)
                        raise
            
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        
        return decorator
    
    def shutdown(self) -> None:
        """Остановка телеметрии."""
        if self.tracer_provider:
            self.tracer_provider.shutdown()
            logger.info("✅ OpenTelemetry shutdown complete")


# Глобальный экземпляр
_telemetry: Optional[Telemetry] = None


def setup_telemetry(
    app=None,
    service_name: str = "rentscout",
    service_version: str = "1.0.0",
    exporter: str = "console",
    **kwargs
) -> Telemetry:
    """
    Настройка телеметрии для приложения.
    
    Args:
        app: FastAPI приложение
        service_name: Имя сервиса
        service_version: Версия сервиса
        exporter: Тип экспортера (console, jaeger, otlp)
        **kwargs: Дополнительные параметры для TelemetryConfig
    
    Returns:
        Telemetry объект
    """
    global _telemetry
    
    config = TelemetryConfig(
        service_name=service_name,
        service_version=service_version,
        exporter=exporter,
        **kwargs
    )
    
    _telemetry = Telemetry(config)
    
    if app:
        _telemetry.instrument_fastapi(app)
    
    return _telemetry


def get_telemetry() -> Optional[Telemetry]:
    """Получает глобальный экземпляр телеметрии."""
    return _telemetry


# Утилита для ручного создания спанов
def trace_span(name: str, **attributes):
    """
    Декоратор для быстрого трейсинга.
    
    Example:
        @trace_span("process_parser", parser="avito")
        async def parse_avito():
            ...
    """
    telemetry = get_telemetry()
    if telemetry:
        return telemetry.trace(name)
    
    # Если телеметрия не настроена, возвращаем оригинальную функцию
    def decorator(func):
        return func
    return decorator


# Импортируем asyncio для проверки
import asyncio


__all__ = [
    "Telemetry",
    "TelemetryConfig",
    "setup_telemetry",
    "get_telemetry",
    "trace_span",
    "OTEL_AVAILABLE",
]
