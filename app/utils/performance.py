"""
Утилиты мониторинга производительности для отслеживания метрик приложения.
Предоставляет декораторы и контекстные менеджеры для простого отслеживания производительности.
"""
import asyncio
import functools
import time
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Callable, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime

from prometheus_client import Counter, Histogram, Gauge, Summary
from app.utils.logger import logger


# Performance metrics
FUNCTION_CALLS = Counter(
    'function_calls_total',
    'Total function calls',
    ['function_name', 'status']
)

FUNCTION_DURATION = Histogram(
    'function_duration_seconds',
    'Function execution duration',
    ['function_name'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
)

SLOW_QUERIES = Counter(
    'slow_operations_total',
    'Total slow operations (>1s)',
    ['operation_type', 'threshold']
)

MEMORY_USAGE = Gauge(
    'memory_usage_bytes',
    'Current memory usage in bytes'
)

ACTIVE_TASKS = Gauge(
    'active_tasks',
    'Number of active async tasks'
)


@dataclass
class PerformanceStats:
    """Контейнер для статистики производительности."""
    
    operation_name: str
    start_time: float = field(default_factory=time.perf_counter)
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error: Optional[Exception] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def finish(self, success: bool = True, error: Optional[Exception] = None):
        """Отметить операцию как завершенную."""
        self.end_time = time.perf_counter()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error = error
    
    def to_dict(self) -> dict:
        """Преобразовать в словарь."""
        return {
            "operation": self.operation_name,
            "duration_ms": round(self.duration * 1000, 2) if self.duration else None,
            "success": self.success,
            "error": str(self.error) if self.error else None,
            "metadata": self.metadata
        }


class PerformanceMonitor:
    """Центральный менеджер мониторинга производительности."""
    
    def __init__(self):
        self.stats_history: list[PerformanceStats] = []
        self.max_history = 1000
        self._lock = asyncio.Lock()
    
    async def record(self, stats: PerformanceStats):
        """Записать статистику производительности."""
        async with self._lock:
            self.stats_history.append(stats)
            
            # Trim history if needed
            if len(self.stats_history) > self.max_history:
                self.stats_history = self.stats_history[-self.max_history:]
            
            # Log slow operations
            if stats.duration and stats.duration > 1.0:
                logger.warning(
                    f"Slow operation detected: {stats.operation_name} "
                    f"took {stats.duration:.2f}s"
                )
                SLOW_QUERIES.labels(
                    operation_type=stats.operation_name,
                    threshold="1s"
                ).inc()
    
    def get_stats(
        self,
        operation_name: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """Получить статистику производительности."""
        filtered = self.stats_history
        
        if operation_name:
            filtered = [s for s in filtered if s.operation_name == operation_name]
        
        return [s.to_dict() for s in filtered[-limit:]]
    
    def get_summary(self) -> dict:
        """Получить сводную статистику."""
        if not self.stats_history:
            return {"message": "No statistics available"}
        
        total_ops = len(self.stats_history)
        successful = sum(1 for s in self.stats_history if s.success)
        failed = total_ops - successful
        
        durations = [s.duration for s in self.stats_history if s.duration]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "total_operations": total_ops,
            "successful": successful,
            "failed": failed,
            "success_rate": round(successful / total_ops * 100, 2),
            "avg_duration_ms": round(avg_duration * 1000, 2),
            "max_duration_ms": round(max(durations) * 1000, 2) if durations else 0,
            "min_duration_ms": round(min(durations) * 1000, 2) if durations else 0
        }


# Global monitor instance
perf_monitor = PerformanceMonitor()


def track_performance(operation_name: Optional[str] = None):
    """
    Декоратор для отслеживания производительности функции.
    
    Пример:
        @track_performance("user_login")
        async def login_user(username: str):
            # Логика входа
    """
    def decorator(func: Callable):
        op_name = operation_name or func.__name__
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            stats = PerformanceStats(operation_name=op_name)
            
            # Record function call
            FUNCTION_CALLS.labels(
                function_name=op_name,
                status='started'
            ).inc()
            
            try:
                # Execute function
                result = await func(*args, **kwargs)
                
                stats.finish(success=True)
                FUNCTION_CALLS.labels(
                    function_name=op_name,
                    status='success'
                ).inc()
                
                return result
                
            except Exception as e:
                stats.finish(success=False, error=e)
                FUNCTION_CALLS.labels(
                    function_name=op_name,
                    status='error'
                ).inc()
                raise
                
            finally:
                # Record duration
                if stats.duration:
                    FUNCTION_DURATION.labels(
                        function_name=op_name
                    ).observe(stats.duration)
                
                # Store stats
                await perf_monitor.record(stats)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            stats = PerformanceStats(operation_name=op_name)
            
            FUNCTION_CALLS.labels(
                function_name=op_name,
                status='started'
            ).inc()
            
            try:
                result = func(*args, **kwargs)
                stats.finish(success=True)
                FUNCTION_CALLS.labels(
                    function_name=op_name,
                    status='success'
                ).inc()
                return result
                
            except Exception as e:
                stats.finish(success=False, error=e)
                FUNCTION_CALLS.labels(
                    function_name=op_name,
                    status='error'
                ).inc()
                raise
                
            finally:
                if stats.duration:
                    FUNCTION_DURATION.labels(
                        function_name=op_name
                    ).observe(stats.duration)
                
                # Can't await in sync function, skip recording
                logger.debug(f"{op_name}: {stats.duration:.3f}s")
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


@asynccontextmanager
async def track_operation(operation_name: str, metadata: Optional[Dict] = None):
    """
    Контекстный менеджер для отслеживания производительности операции.
    
    Пример:
        async with track_operation("database_query", {"table": "users"}):
            results = await db.query("SELECT * FROM users")
    """
    stats = PerformanceStats(
        operation_name=operation_name,
        metadata=metadata or {}
    )
    
    try:
        yield stats
        stats.finish(success=True)
    except Exception as e:
        stats.finish(success=False, error=e)
        raise
    finally:
        await perf_monitor.record(stats)
        
        if stats.duration:
            FUNCTION_DURATION.labels(
                function_name=operation_name
            ).observe(stats.duration)


@contextmanager
def track_sync_operation(operation_name: str, metadata: Optional[Dict] = None):
    """
    Синхронный контекстный менеджер для отслеживания производительности операции.
    
    Пример:
        with track_sync_operation("file_processing"):
            process_file("data.csv")
    """
    stats = PerformanceStats(
        operation_name=operation_name,
        metadata=metadata or {}
    )
    
    try:
        yield stats
        stats.finish(success=True)
    except Exception as e:
        stats.finish(success=False, error=e)
        raise
    finally:
        if stats.duration:
            FUNCTION_DURATION.labels(
                function_name=operation_name
            ).observe(stats.duration)
            
            logger.debug(
                f"{operation_name}: {stats.duration:.3f}s "
                f"(success: {stats.success})"
            )


def measure_time(func: Callable) -> Callable:
    """
    Простой декоратор для измерения и логирования времени выполнения функции.
    
    Пример:
        @measure_time
        def slow_function():
            time.sleep(2)
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return await func(*args, **kwargs)
        finally:
            duration = time.perf_counter() - start
            logger.info(f"{func.__name__} took {duration:.3f}s")
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            duration = time.perf_counter() - start
            logger.info(f"{func.__name__} took {duration:.3f}s")
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper
