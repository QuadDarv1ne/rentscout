"""Tests for circuit breaker."""

import pytest
import time
import asyncio
from unittest.mock import Mock, AsyncMock

from app.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
    get_circuit_breaker,
)


class TestCircuitBreaker:
    """Тесты для circuit breaker."""

    def test_circuit_breaker_initialization(self):
        """Тест инициализации circuit breaker."""
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=10.0)

        assert cb.name == "test"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_circuit_breaker_closed_state_success(self):
        """Тест успешного вызова в CLOSED состоянии."""
        cb = CircuitBreaker("test", failure_threshold=3)

        def success_func():
            return "success"

        result = cb.call(success_func)

        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_closed_state_failure(self):
        """Тест ошибки в CLOSED состоянии."""
        cb = CircuitBreaker("test", failure_threshold=3)

        def failing_func():
            raise ValueError("Test error")

        # Первая ошибка не открывает цепь
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1

    def test_circuit_breaker_opens_after_threshold(self):
        """Тест открытия цепи после достижения порога ошибок."""
        cb = CircuitBreaker("test", failure_threshold=2)

        def failing_func():
            raise ValueError("Test error")

        # Первая ошибка
        with pytest.raises(ValueError):
            cb.call(failing_func)

        # Вторая ошибка открывает цепь
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

    def test_circuit_breaker_open_prevents_calls(self):
        """Тест что открытая цепь предотвращает вызовы."""
        cb = CircuitBreaker("test", failure_threshold=1)

        def failing_func():
            raise ValueError("Test error")

        def success_func():
            return "success"

        # Открываем цепь
        with pytest.raises(ValueError):
            cb.call(failing_func)

        # Теперь даже успешная функция не выполняется
        with pytest.raises(CircuitBreakerOpen):
            cb.call(success_func)

    def test_circuit_breaker_half_open_recovery(self):
        """Тест восстановления через HALF_OPEN состояние."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1, success_threshold=1)

        def failing_func():
            raise ValueError("Test error")

        def success_func():
            return "success"

        # Открываем цепь
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Ждем recovery timeout
        time.sleep(0.2)

        # Пробуем вызвать функцию - попытаемся перейти в HALF_OPEN
        # На первый вызов функция выполнится (для проверки восстановления)
        result = cb.call(success_func)
        
        assert result == "success"
        assert cb.state == CircuitState.CLOSED  # Восстановление успешно

    def test_circuit_breaker_reset(self):
        """Тест ручного сброса circuit breaker."""
        cb = CircuitBreaker("test", failure_threshold=1)

        def failing_func():
            raise ValueError("Test error")

        # Открываем цепь
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Сбрасываем
        cb.reset()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_get_status(self):
        """Тест получения статуса circuit breaker."""
        cb = CircuitBreaker("test", failure_threshold=3)

        status = cb.get_status()

        assert status["name"] == "test"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0

    def test_circuit_breaker_multiple_failures_in_half_open(self):
        """Тест что ошибка в HALF_OPEN состоянии открывает цепь."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1, success_threshold=2)

        def failing_func():
            raise ValueError("Test error")

        # Открываем цепь
        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Ждем recovery timeout
        time.sleep(0.2)

        # Попытаемся восстановиться (войдем в HALF_OPEN)
        # На первой попытке function не будет выполнена (уже checked)
        # На второй попытке:
        with pytest.raises(ValueError):
            cb.call(failing_func)

        # Вернемся в OPEN
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerAsync:
    """Тесты для асинхронного circuit breaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_success(self):
        """Тест успешного асинхронного вызова."""
        cb = CircuitBreaker("test")

        async def success_func():
            return "success"

        result = await cb.call_async(success_func)

        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_failure(self):
        """Тест асинхронной ошибки."""
        cb = CircuitBreaker("test", failure_threshold=1)

        async def failing_func():
            raise ValueError("Test error")

        # Открываем цепь
        with pytest.raises(ValueError):
            await cb.call_async(failing_func)

        assert cb.state == CircuitState.OPEN

        # Теперь цепь открыта
        with pytest.raises(CircuitBreakerOpen):
            await cb.call_async(failing_func)

    @pytest.mark.asyncio
    async def test_circuit_breaker_async_recovery(self):
        """Тест восстановления асинхронного circuit breaker."""
        cb = CircuitBreaker(
            "test",
            failure_threshold=1,
            recovery_timeout=0.1,
            success_threshold=1,
        )

        async def failing_func():
            raise ValueError("Test error")

        async def success_func():
            return "success"

        # Открываем цепь
        with pytest.raises(ValueError):
            await cb.call_async(failing_func)

        assert cb.state == CircuitState.OPEN

        # Ждем
        await asyncio.sleep(0.2)

        # Восстанавливаемся
        result = await cb.call_async(success_func)
        assert result == "success"


class TestCircuitBreakerFactory:
    """Тесты для factory функции."""

    def test_get_circuit_breaker(self):
        """Тест получения circuit breaker по источнику."""
        cb1 = get_circuit_breaker("avito")
        cb2 = get_circuit_breaker("avito")

        # Должна быть одна и та же instance
        assert cb1 is cb2
        assert cb1.name == "avito"

    def test_get_circuit_breaker_creates_new(self):
        """Тест создания нового circuit breaker для неизвестного источника."""
        cb = get_circuit_breaker("unknown_source")

        assert cb.name == "unknown_source"
        assert cb.state == CircuitState.CLOSED
