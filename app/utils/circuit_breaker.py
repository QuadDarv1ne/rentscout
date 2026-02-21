"""
Circuit Breaker паттерн для защиты от сбоев внешних сервисов.

Реализация на основе статьи Martin Fowler:
https://martinfowler.com/bliki/CircuitBreaker.html

Состояния:
- CLOSED: Нормальная работа, ошибки логируются
- OPEN: Быстрый отказ, запросы не выполняются
- HALF_OPEN: Проверка восстановления сервиса
"""

import asyncio
import time
from enum import Enum
from typing import Optional, Callable, Any, Awaitable
from dataclasses import dataclass, field
from collections import defaultdict

from app.utils.logger import logger


class CircuitState(str, Enum):
    """Состояния circuit breaker."""
    CLOSED = "closed"      # Нормальная работа
    OPEN = "open"          # Быстрый отказ
    HALF_OPEN = "half_open"  # Проверка восстановления


@dataclass
class CircuitBreakerConfig:
    """Конфигурация circuit breaker."""
    failure_threshold: int = 5          # Количество ошибок для открытия
    success_threshold: int = 3          # Количество успехов для закрытия
    timeout: float = 60.0               # Время до перехода в half-open (сек)
    half_open_max_calls: int = 3        # Максимум тестовых вызовов в half-open
    expected_exceptions: tuple = (Exception,)  # Ожидаемые исключения


@dataclass
class CircuitStats:
    """Статистика circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0  # Отклонённые из-за open состояния
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    state_changes: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreakerOpen(Exception):
    """Исключение при открытом circuit breaker."""
    def __init__(self, service_name: str, time_until_retry: float):
        self.service_name = service_name
        self.time_until_retry = time_until_retry
        super().__init__(
            f"Circuit breaker '{service_name}' is OPEN. "
            f"Retry after {time_until_retry:.1f}s"
        )


class CircuitBreaker:
    """
    Circuit breaker для защиты от каскадных сбоев.
    
    Пример использования:
        breaker = CircuitBreaker("avito_api")
        
        @breaker
        async def fetch_data():
            return await http_client.get(url)
    """
    
    # Глобальное хранилище breaker'ов по сервисам
    _breakers: dict[str, 'CircuitBreaker'] = {}
    _lock = asyncio.Lock()
    
    def __init__(
        self,
        service_name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.service_name = service_name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self._failure_time: Optional[float] = None
        self._half_open_calls: int = 0
    
    @classmethod
    async def get_breaker(
        cls,
        service_name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> 'CircuitBreaker':
        """Получить или создать breaker для сервиса."""
        async with cls._lock:
            if service_name not in cls._breakers:
                cls._breakers[service_name] = cls(service_name, config)
                logger.info(f"Created circuit breaker for '{service_name}'")
            return cls._breakers[service_name]
    
    @classmethod
    def get_all_breakers(cls) -> dict[str, 'CircuitBreaker']:
        """Получить все breaker'ы."""
        return cls._breakers.copy()
    
    @classmethod
    async def reset_all(cls) -> None:
        """Сбросить все breaker'ы в CLOSED."""
        async with cls._lock:
            for breaker in cls._breakers.values():
                breaker.state = CircuitState.CLOSED
                breaker.stats.consecutive_failures = 0
                breaker.stats.consecutive_successes = 0
                breaker.stats.state_changes += 1
            logger.info("All circuit breakers reset to CLOSED")
    
    def __call__(self, func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        """Декоратор для защиты функций."""
        async def wrapper(*args, **kwargs) -> Any:
            return await self.call(func, *args, **kwargs)
        return wrapper
    
    async def call(
        self,
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> Any:
        """
        Вызвать функцию с защитой circuit breaker.
        
        Args:
            func: Асинхронная функция для вызова
            *args, **kwargs: Аргументы функции
            
        Returns:
            Результат функции
            
        Raises:
            CircuitBreakerOpen: Если breaker в состоянии OPEN
        """
        self.stats.total_calls += 1
        
        # Проверка состояния
        if self.state == CircuitState.OPEN:
            time_until_retry = self._time_until_retry()
            
            if time_until_retry > 0:
                self.stats.rejected_calls += 1
                logger.warning(
                    f"Circuit breaker '{self.service_name}' is OPEN. "
                    f"Rejecting call. Retry in {time_until_retry:.1f}s"
                )
                raise CircuitBreakerOpen(self.service_name, time_until_retry)
            
            # Переход в HALF_OPEN
            self._transition_to(CircuitState.HALF_OPEN)
            self._half_open_calls = 0
        
        # Выполнение вызова
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except self.config.expected_exceptions as e:
            await self._on_failure()
            raise
    
    async def _on_success(self) -> None:
        """Обработка успешного вызова."""
        self.stats.successful_calls += 1
        self.stats.last_success_time = time.time()
        self.stats.consecutive_failures = 0
        self.stats.consecutive_successes += 1
        
        if self.state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            
            # Если достаточно успехов - закрываем
            if self.stats.consecutive_successes >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
                logger.info(
                    f"Circuit breaker '{self.service_name}' CLOSED after "
                    f"{self.stats.consecutive_successes} successful calls"
                )
    
    async def _on_failure(self) -> None:
        """Обработка неудачного вызова."""
        self.stats.failed_calls += 1
        self.stats.last_failure_time = time.time()
        self.stats.consecutive_successes = 0
        self.stats.consecutive_failures += 1
        
        if self.state == CircuitState.HALF_OPEN:
            # При ошибке в half-open - сразу открываем
            self._transition_to(CircuitState.OPEN)
            logger.warning(
                f"Circuit breaker '{self.service_name}' OPEN after failure in HALF_OPEN"
            )
        
        elif self.state == CircuitState.CLOSED:
            # Проверка порога ошибок
            if self.stats.consecutive_failures >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.warning(
                    f"Circuit breaker '{self.service_name}' OPEN after "
                    f"{self.stats.consecutive_failures} consecutive failures"
                )
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """Переход в новое состояние."""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            self.stats.state_changes += 1
            
            logger.info(
                f"Circuit breaker '{self.service_name}': "
                f"{old_state.value} → {new_state.value}"
            )
    
    def _time_until_retry(self) -> float:
        """Время до перехода в HALF_OPEN."""
        if self._failure_time is None:
            return 0
        
        elapsed = time.time() - self._failure_time
        return max(0, self.config.timeout - elapsed)
    
    def get_stats(self) -> dict:
        """Получить статистику breaker."""
        return {
            'service_name': self.service_name,
            'state': self.state.value,
            'stats': {
                'total_calls': self.stats.total_calls,
                'successful_calls': self.stats.successful_calls,
                'failed_calls': self.stats.failed_calls,
                'rejected_calls': self.stats.rejected_calls,
                'consecutive_failures': self.stats.consecutive_failures,
                'consecutive_successes': self.stats.consecutive_successes,
                'state_changes': self.stats.state_changes,
            },
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'success_threshold': self.config.success_threshold,
                'timeout': self.config.timeout,
            }
        }


# ============================================================================
# Circuit Breaker для парсеров
# ============================================================================

class ParserCircuitBreaker:
    """
    Circuit breaker специально для парсеров.
    
    Автоматически создаёт breaker'ы для каждого парсера.
    """
    
    _breakers: dict[str, CircuitBreaker] = {}
    
    @classmethod
    async def get_breaker(cls, parser_name: str) -> CircuitBreaker:
        """Получить breaker для парсера."""
        if parser_name not in cls._breakers:
            config = CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout=60.0,
                expected_exceptions=(Exception,)
            )
            cls._breakers[parser_name] = await CircuitBreaker.get_breaker(
                parser_name,
                config
            )
        return cls._breakers[parser_name]
    
    @classmethod
    async def call_parser(
        cls,
        parser_name: str,
        func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs
    ) -> Any:
        """
        Вызвать метод парсера с circuit breaker защитой.
        
        Args:
            parser_name: Название парсера (AvitoParser, CianParser, etc.)
            func: Асинхронная функция парсера
            *args, **kwargs: Аргументы функции
            
        Returns:
            Результат парсинга
        """
        breaker = await cls.get_breaker(parser_name)
        
        try:
            return await breaker.call(func, *args, **kwargs)
        except CircuitBreakerOpen as e:
            logger.warning(f"Parser '{parser_name}' circuit breaker open: {e}")
            return []  # Возвращаем пустой результат вместо ошибки
    
    @classmethod
    def get_all_stats(cls) -> dict[str, dict]:
        """Получить статистику всех breaker'ов парсеров."""
        return {
            name: breaker.get_stats()
            for name, breaker in cls._breakers.items()
        }


# ============================================================================
# Декораторы для удобного использования
# ============================================================================

def circuit_breaker(
    service_name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> Callable:
    """
    Декоратор circuit breaker.
    
    Пример:
        @circuit_breaker("avito_api")
        async def fetch_avito_data():
            ...
    """
    async def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        breaker = await CircuitBreaker.get_breaker(service_name, config)
        
        async def wrapper(*args, **kwargs) -> Any:
            return await breaker.call(func, *args, **kwargs)
        
        return wrapper
    
    return decorator


# ============================================================================
# Экспорт
# ============================================================================

__all__ = [
    # Классы
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerOpen",
    "CircuitState",
    "CircuitStats",
    "ParserCircuitBreaker",
    
    # Декораторы
    "circuit_breaker",
]
