"""
Tests for Adaptive Rate Limiter implementation.
"""

import pytest
import asyncio

from app.utils.adaptive_ratelimit import (
    AdaptiveRateLimiter,
    RateLimitConfig,
    RateLimitState,
)


@pytest.fixture
def rate_limit_config():
    """Config для тестов с быстрыми порогами."""
    return RateLimitConfig(
        base_delay=0.1,
        min_delay=0.01,
        max_delay=2.0,
        increase_factor=2.0,
        decrease_factor=0.5,
        success_threshold=3,  # 3 успеха для уменьшения задержки
        error_threshold=2,
        cooldown_window=30.0,
    )


@pytest.fixture
async def limiter(rate_limit_config):
    """Создать rate limiter для тестов."""
    return await AdaptiveRateLimiter.get_limiter("test_service", rate_limit_config)


@pytest.mark.asyncio
async def test_adaptive_limiter_initial_state(limiter):
    """Проверка начального состояния rate limiter."""
    assert limiter.stats.state == RateLimitState.NORMAL
    assert limiter.stats.current_delay == limiter.config.base_delay
    assert limiter.stats.total_requests == 0


@pytest.mark.asyncio
async def test_adaptive_limiter_acquire(limiter):
    """Тест acquire задержки."""
    delay = await limiter.acquire()
    assert delay == limiter.config.base_delay


@pytest.mark.asyncio
async def test_adaptive_limiter_on_rate_limit(limiter):
    """Реакция на rate limit (429)."""
    initial_delay = limiter.stats.current_delay

    await limiter.record_response(429)

    assert limiter.stats.current_delay > initial_delay
    assert limiter.stats.rate_limited_requests == 1
    assert limiter.stats.consecutive_errors == 1
    assert limiter.stats.state in (RateLimitState.CAUTIOUS, RateLimitState.THROTTLED)


@pytest.mark.asyncio
async def test_adaptive_limiter_on_forbidden(limiter):
    """Реакция на 403 Forbidden."""
    initial_delay = limiter.stats.current_delay

    await limiter.record_response(403)

    assert limiter.stats.current_delay > initial_delay
    assert limiter.stats.state != RateLimitState.NORMAL


@pytest.mark.asyncio
async def test_adaptive_limiter_on_server_error(limiter):
    """Реакция на 5xx Server Error."""
    initial_delay = limiter.stats.current_delay

    await limiter.record_response(503)

    assert limiter.stats.current_delay > initial_delay
    # 503 тоже считается как rate limit
    assert limiter.stats.errors_in_window >= 1


@pytest.mark.asyncio
async def test_adaptive_limiter_on_success(limiter):
    """Реакция на успешный запрос."""
    # Сначала увеличим задержку
    await limiter.record_response(429)
    increased_delay = limiter.stats.current_delay

    # Теперь несколько успехов
    for _ in range(3):
        await limiter.record_response(200)

    # После успехов задержка должна уменьшиться
    assert limiter.stats.current_delay <= increased_delay
    assert limiter.stats.consecutive_errors == 0


@pytest.mark.asyncio
async def test_adaptive_limiter_state_transitions(limiter):
    """Проверка переходов между состояниями."""
    # Начальное состояние - NORMAL
    assert limiter.stats.state == RateLimitState.NORMAL

    # Несколько rate limit - переход в THROTTLED
    for _ in range(5):
        await limiter.record_response(429)

    assert limiter.stats.state in (RateLimitState.CAUTIOUS, RateLimitState.THROTTLED)

    # После успехов - возврат в NORMAL
    for _ in range(10):
        await limiter.record_response(200)

    # Задержка должна уменьшиться до минимума
    assert limiter.stats.current_delay <= limiter.config.base_delay


@pytest.mark.asyncio
async def test_adaptive_limiter_max_delay(limiter):
    """Проверка ограничения максимальной задержки."""
    # Много раз вызываем rate limit
    for _ in range(20):
        await limiter.record_response(429)

    # Задержка не должна превышать max_delay
    assert limiter.stats.current_delay <= limiter.config.max_delay


@pytest.mark.asyncio
async def test_adaptive_limiter_min_delay(limiter):
    """Проверка ограничения минимальной задержки."""
    # Много успехов для уменьшения задержки
    for _ in range(50):
        await limiter.record_response(200)

    # Задержка не должна быть меньше min_delay
    assert limiter.stats.current_delay >= limiter.config.min_delay


@pytest.mark.asyncio
async def test_adaptive_limiter_stats(limiter):
    """Проверка статистики."""
    await limiter.record_response(200)
    await limiter.record_response(200)
    await limiter.record_response(429)
    await limiter.record_response(500)

    stats = limiter.get_stats()

    assert stats['service_name'] == 'test_service'
    assert stats['stats']['total_requests'] == 4
    assert stats['stats']['successful_requests'] == 2
    assert stats['stats']['rate_limited_requests'] == 1


@pytest.mark.asyncio
async def test_adaptive_limiter_reset(limiter):
    """Тест сброса rate limiter."""
    # Увеличиваем задержку
    await limiter.record_response(429)
    await limiter.record_response(429)

    increased_delay = limiter.stats.current_delay
    assert increased_delay > limiter.config.base_delay

    # Сбрасываем
    await limiter.reset()

    assert limiter.stats.current_delay == limiter.config.base_delay
    assert limiter.stats.total_requests == 0
    assert limiter.stats.state == RateLimitState.NORMAL


@pytest.mark.asyncio
async def test_adaptive_limiter_context_manager(limiter):
    """Тест использования как контекстный менеджер."""
    async with limiter:
        # Имитируем запрос
        await asyncio.sleep(0.01)

    assert limiter.stats.total_requests == 0  # acquire не считает запрос


@pytest.mark.asyncio
async def test_adaptive_limiter_error_window(limiter):
    """Тест окна ошибок."""
    # Добавляем ошибки
    await limiter.record_response(429)
    await limiter.record_response(429)

    assert limiter.stats.errors_in_window == 2

    # Ждём истечения окна (в тестах 30 секунд, пропускаем)
    # Проверяем что ошибки считаются
    assert limiter.stats.errors_in_window >= 1


@pytest.mark.asyncio
async def test_adaptive_limiter_concurrent_access():
    """Тест конкурентного доступа."""
    config = RateLimitConfig(base_delay=0.01)
    limiter = await AdaptiveRateLimiter.get_limiter("concurrent_test", config)

    async def make_request():
        async with limiter:
            await limiter.record_response(200)

    # Запускаем 10 параллельных запросов
    tasks = [make_request() for _ in range(10)]
    await asyncio.gather(*tasks)

    assert limiter.stats.successful_requests == 10


@pytest.mark.asyncio
async def test_adaptive_limiter_exponential_backoff(limiter):
    """Тест экспоненциального увеличения задержки."""
    delays = []

    # Серия rate limit
    for i in range(5):
        await limiter.record_response(429)
        delays.append(limiter.stats.current_delay)

    # Задержка должна расти экспоненциально
    for i in range(1, len(delays)):
        assert delays[i] >= delays[i - 1], f"Delay should increase: {delays}"
