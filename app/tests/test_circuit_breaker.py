"""
Tests for Circuit Breaker pattern implementation.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitState,
    ParserCircuitBreaker,
)


@pytest.fixture
def circuit_breaker_config():
    """Config для тестов с быстрыми порогами."""
    return CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout=1.0,  # 1 секунда для тестов
        half_open_max_calls=2,
    )


@pytest.fixture
async def breaker(circuit_breaker_config):
    """Создать circuit breaker для тестов."""
    return await CircuitBreaker.get_breaker("test_service", circuit_breaker_config)


@pytest.mark.asyncio
async def test_circuit_breaker_initial_state(breaker):
    """Проверка начального состояния circuit breaker."""
    assert breaker.state == CircuitState.CLOSED
    assert breaker.stats.total_calls == 0
    assert breaker.stats.consecutive_failures == 0


@pytest.mark.asyncio
async def test_circuit_breaker_closed_on_success(breaker):
    """Circuit breaker остаётся CLOSED при успешных вызовах."""
    async def success_func():
        return "success"

    result = await breaker.call(success_func)
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.stats.successful_calls == 1


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures(breaker):
    """Circuit breaker переходит в OPEN после серии ошибок."""
    async def failing_func():
        raise ValueError("Test error")

    # Вызываем 3 раза (порог failure_threshold)
    for _ in range(3):
        with pytest.raises(ValueError):
            await breaker.call(failing_func)

    # После 3 ошибок breaker должен открыться
    assert breaker.state == CircuitState.OPEN
    assert breaker.stats.consecutive_failures == 3
    assert breaker.stats.failed_calls == 3


@pytest.mark.asyncio
async def test_circuit_breaker_rejects_when_open(breaker):
    """Circuit breaker отклоняет вызовы в состоянии OPEN."""
    async def failing_func():
        raise ValueError("Test error")

    # Открываем breaker
    for _ in range(3):
        with pytest.raises(ValueError):
            await breaker.call(failing_func)

    assert breaker.state == CircuitState.OPEN

    # Следующий вызов должен быть отклонён
    with pytest.raises(CircuitBreakerOpen):
        await breaker.call(failing_func)

    assert breaker.stats.rejected_calls == 1


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_after_timeout(breaker):
    """Circuit breaker переходит в HALF_OPEN после timeout."""
    async def failing_func():
        raise ValueError("Test error")

    # Открываем breaker
    for _ in range(3):
        with pytest.raises(ValueError):
            await breaker.call(failing_func)

    assert breaker.state == CircuitState.OPEN

    # Ждём timeout (1 секунда в конфиге тестов)
    await asyncio.sleep(1.1)

    # Следующий вызов должен перевести в HALF_OPEN
    with pytest.raises(ValueError):
        await breaker.call(failing_func)

    # После ошибки в HALF_OPEN - снова OPEN
    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_circuit_breaker_closes_after_successes(breaker):
    """Circuit breaker закрывается после успешных вызовов в HALF_OPEN."""
    call_count = 0

    async def sometimes_fails():
        nonlocal call_count
        call_count += 1
        if call_count <= 3:
            raise ValueError("Test error")
        return "success"

    # Открываем breaker
    for _ in range(3):
        with pytest.raises(ValueError):
            await breaker.call(sometimes_fails)

    assert breaker.state == CircuitState.OPEN

    # Ждём timeout
    await asyncio.sleep(1.1)

    # Успешные вызовы в HALF_OPEN
    result = await breaker.call(sometimes_fails)
    assert result == "success"

    # Ещё один успех должен закрыть breaker
    result = await breaker.call(sometimes_fails)
    assert result == "success"

    assert breaker.state == CircuitState.CLOSED
    assert breaker.stats.consecutive_successes == 0  # Сброшен после закрытия


@pytest.mark.asyncio
async def test_circuit_breaker_stats(breaker):
    """Проверка статистики circuit breaker."""
    async def success_func():
        return "ok"

    await breaker.call(success_func)
    await breaker.call(success_func)

    stats = breaker.get_stats()

    assert stats['service_name'] == 'test_service'
    assert stats['state'] == 'closed'
    assert stats['stats']['total_calls'] == 2
    assert stats['stats']['successful_calls'] == 2
    assert stats['stats']['failed_calls'] == 0


@pytest.mark.asyncio
async def test_parser_circuit_breaker():
    """Тест ParserCircuitBreaker."""
    parser_name = "TestParser"

    async def parser_func():
        return ["result1", "result2"]

    result = await ParserCircuitBreaker.call_parser(parser_name, parser_func)
    assert result == ["result1", "result2"]

    # Проверяем что breaker создан
    stats = ParserCircuitBreaker.get_all_stats()
    assert parser_name in stats


@pytest.mark.asyncio
async def test_circuit_breaker_reset():
    """Тест сброса circuit breaker."""
    config = CircuitBreakerConfig(failure_threshold=2)
    breaker = await CircuitBreaker.get_breaker("reset_test", config)

    async def failing_func():
        raise ValueError("Error")

    # Открываем breaker
    for _ in range(2):
        with pytest.raises(ValueError):
            await breaker.call(failing_func)

    assert breaker.state == CircuitState.OPEN

    # Сбрасываем
    await CircuitBreaker.reset_all()

    assert breaker.state == CircuitState.CLOSED
    assert breaker.stats.consecutive_failures == 0


@pytest.mark.asyncio
async def test_circuit_breaker_concurrent_access():
    """Тест конкурентного доступа к circuit breaker."""
    config = CircuitBreakerConfig(failure_threshold=10)
    breaker = await CircuitBreaker.get_breaker("concurrent_test", config)

    async def success_func():
        await asyncio.sleep(0.01)
        return "ok"

    # Запускаем 10 параллельных вызовов
    tasks = [breaker.call(success_func) for _ in range(10)]
    results = await asyncio.gather(*tasks)

    assert len(results) == 10
    assert all(r == "ok" for r in results)
    assert breaker.stats.total_calls == 10
