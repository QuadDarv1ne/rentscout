"""Circuit breaker паттерн для защиты от каскадных ошибок."""

import asyncio
import time
from enum import Enum
from typing import Callable, Optional, Any

from app.utils.logger import logger


class CircuitState(str, Enum):
    """Состояния circuit breaker."""

    CLOSED = "closed"  # Нормальная работа
    OPEN = "open"  # Отключен после ошибок
    HALF_OPEN = "half_open"  # Пытается восстановиться


class CircuitBreaker:
    """
    Circuit breaker для защиты от каскадных ошибок.

    Отключает операцию после N ошибок в течение временного окна,
    затем позволяет одной операции попробовать восстановиться.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ):
        """
        Инициализация circuit breaker.

        Args:
            name: Имя цепи для логирования
            failure_threshold: Количество ошибок для открытия цепи
            recovery_timeout: Время ожидания перед попыткой восстановления (сек)
            success_threshold: Количество успешных операций для закрытия цепи
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполняет функцию через circuit breaker.

        Args:
            func: Функция для выполнения
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы

        Returns:
            Результат функции

        Raises:
            CircuitBreakerOpen: Если цепь открыта
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' is half-open, attempting recovery...")
            else:
                raise CircuitBreakerOpen(f"Circuit '{self.name}' is open")

        try:
            result = func(*args, **kwargs)

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._close()
            else:
                # CLOSED состояние - успешный вызов
                self.failure_count = 0
                self.success_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                # Неудача в HALF_OPEN состоянии - вернемся в OPEN
                self._open()
            elif self.failure_count >= self.failure_threshold:
                # Достаточно ошибок в CLOSED состоянии - открываем цепь
                self._open()

            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Асинхронное выполнение функции через circuit breaker.

        Args:
            func: Асинхронная функция для выполнения
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы

        Returns:
            Результат функции

        Raises:
            CircuitBreakerOpen: Если цепь открыта
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}' is half-open, attempting recovery...")
            else:
                raise CircuitBreakerOpen(f"Circuit '{self.name}' is open")

        try:
            result = await func(*args, **kwargs)

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self._close()
            else:
                # CLOSED состояние - успешный вызов
                self.failure_count = 0
                self.success_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                # Неудача в HALF_OPEN состоянии - вернемся в OPEN
                self._open()
            elif self.failure_count >= self.failure_threshold:
                # Достаточно ошибок в CLOSED состоянии - открываем цепь
                self._open()

            raise

    def _should_attempt_reset(self) -> bool:
        """Проверяет можно ли попытаться восстановиться."""
        if self.opened_at is None:
            return True

        elapsed = time.time() - self.opened_at
        return elapsed >= self.recovery_timeout

    def _open(self) -> None:
        """Открывает цепь."""
        self.state = CircuitState.OPEN
        self.opened_at = time.time()
        self.success_count = 0
        logger.error(
            f"Circuit breaker '{self.name}' is OPEN. "
            f"Failing after {self.failure_count} failures. "
            f"Will retry in {self.recovery_timeout}s."
        )

    def _close(self) -> None:
        """Закрывает цепь."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.opened_at = None
        logger.info(f"Circuit breaker '{self.name}' is CLOSED. Recovery successful.")

    def reset(self) -> None:
        """Вручную сбрасывает цепь."""
        self._close()

    def get_status(self) -> dict:
        """Возвращает статус цепи."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "opened_at": self.opened_at,
        }


class CircuitBreakerOpen(Exception):
    """Исключение когда цепь открыта."""

    pass


# Глобальные circuit breakers для каждого источника
circuit_breakers = {
    "avito": CircuitBreaker("avito", failure_threshold=5, recovery_timeout=300.0),
    "cian": CircuitBreaker("cian", failure_threshold=5, recovery_timeout=300.0),
    "ostrovok": CircuitBreaker("ostrovok", failure_threshold=5, recovery_timeout=300.0),
    "otello": CircuitBreaker("otello", failure_threshold=5, recovery_timeout=300.0),
    "tvil": CircuitBreaker("tvil", failure_threshold=5, recovery_timeout=300.0),
    "yandex_travel": CircuitBreaker("yandex_travel", failure_threshold=5, recovery_timeout=300.0),
}


def get_circuit_breaker(source: str) -> CircuitBreaker:
    """Получает circuit breaker для источника."""
    if source not in circuit_breakers:
        circuit_breakers[source] = CircuitBreaker(source)
    return circuit_breakers[source]
