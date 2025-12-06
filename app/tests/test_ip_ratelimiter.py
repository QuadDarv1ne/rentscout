"""Тесты для IP-based rate limiting."""

import pytest
import asyncio
import time

from app.utils.ip_ratelimiter import IPRateLimiter


@pytest.fixture
def rate_limiter():
    """Фикстура rate limiter с короткими лимитами для тестирования."""
    return IPRateLimiter(
        max_requests=5,
        time_window=10,
        burst_requests=2,
        burst_window=1,
    )


@pytest.mark.asyncio
async def test_rate_limiter_allows_requests(rate_limiter):
    """Тест что запросы разрешены в пределах лимита."""
    ip = "192.168.1.1"
    
    # Первый запрос должен пройти
    allowed, info = await rate_limiter.check_rate_limit(ip, "/api/test")
    assert allowed is True
    assert "remaining" in info
    assert info["remaining"] == 4  # 5 - 1


@pytest.mark.asyncio
async def test_rate_limiter_blocks_excess_requests(rate_limiter):
    """Тест блокировки превышения лимита."""
    ip = "192.168.1.2"
    
    # Делаем максимум разрешенных запросов (с паузами чтобы избежать burst limit)
    for i in range(5):
        allowed, info = await rate_limiter.check_rate_limit(ip, "/api/test")
        assert allowed is True, f"Request {i+1} should be allowed, got: {info}"
        # Пауза между запросами (больше burst_window=1s)
        await asyncio.sleep(1.1)
    
    # Следующий запрос должен быть заблокирован
    allowed, info = await rate_limiter.check_rate_limit(ip, "/api/test")
    assert allowed is False
    assert "error" in info
    assert "retry_after" in info


@pytest.mark.asyncio
async def test_rate_limiter_burst_protection(rate_limiter):
    """Тест защиты от burst запросов."""
    ip = "192.168.1.3"
    
    # Делаем 2 очень быстрых запроса (burst limit)
    for i in range(2):
        allowed, info = await rate_limiter.check_rate_limit(ip, "/api/test")
        assert allowed is True
    
    # Третий быстрый запрос должен быть заблокирован
    allowed, info = await rate_limiter.check_rate_limit(ip, "/api/test")
    assert allowed is False
    assert info["error"] == "Burst rate limit exceeded"
    assert info["window"] == 1


@pytest.mark.asyncio
async def test_rate_limiter_whitelist(rate_limiter):
    """Тест whitelist IP."""
    ip = "127.0.0.1"  # localhost в whitelist по умолчанию
    
    # Делаем много запросов
    for i in range(20):
        allowed, info = await rate_limiter.check_rate_limit(ip, "/api/test")
        assert allowed is True
        assert info.get("whitelisted") is True


@pytest.mark.asyncio
async def test_rate_limiter_reset(rate_limiter):
    """Тест сброса лимита."""
    ip = "192.168.1.4"
    
    # Заполняем лимит
    for i in range(5):
        await rate_limiter.check_rate_limit(ip, "/api/test")
    
    # Проверяем что лимит исчерпан
    allowed, info = await rate_limiter.check_rate_limit(ip, "/api/test")
    assert allowed is False
    
    # Сбрасываем
    rate_limiter.reset(ip)
    
    # Теперь должно работать
    allowed, info = await rate_limiter.check_rate_limit(ip, "/api/test")
    assert allowed is True


@pytest.mark.asyncio
async def test_rate_limiter_different_ips(rate_limiter):
    """Тест что разные IP имеют независимые лимиты."""
    ip1 = "192.168.1.10"
    ip2 = "192.168.1.20"
    
    # Заполняем лимит для первого IP
    for i in range(5):
        await rate_limiter.check_rate_limit(ip1, "/api/test")
    
    # Первый IP должен быть заблокирован
    allowed, _ = await rate_limiter.check_rate_limit(ip1, "/api/test")
    assert allowed is False
    
    # Второй IP должен работать нормально
    allowed, info = await rate_limiter.check_rate_limit(ip2, "/api/test")
    assert allowed is True
    assert info["remaining"] == 4


@pytest.mark.asyncio
async def test_rate_limiter_time_window_expiry(rate_limiter):
    """Тест истечения временного окна."""
    # Создаем limiter с очень коротким окном для теста
    short_limiter = IPRateLimiter(max_requests=2, time_window=2, burst_requests=1, burst_window=1)
    
    ip = "192.168.1.5"
    
    # Заполняем лимит
    await short_limiter.check_rate_limit(ip, "/api/test")
    await asyncio.sleep(1)  # Пауза чтобы избежать burst limit
    await short_limiter.check_rate_limit(ip, "/api/test")
    
    # Лимит исчерпан
    allowed, _ = await short_limiter.check_rate_limit(ip, "/api/test")
    assert allowed is False
    
    # Ждем истечения окна
    await asyncio.sleep(2.5)
    
    # Теперь должно работать
    allowed, info = await short_limiter.check_rate_limit(ip, "/api/test")
    assert allowed is True


def test_rate_limiter_whitelist_management(rate_limiter):
    """Тест управления whitelist."""
    ip = "10.0.0.1"
    
    # Добавляем в whitelist
    rate_limiter.add_to_whitelist(ip)
    assert ip in rate_limiter.whitelist
    
    # Удаляем из whitelist
    rate_limiter.remove_from_whitelist(ip)
    assert ip not in rate_limiter.whitelist


def test_rate_limiter_get_stats(rate_limiter):
    """Тест получения статистики."""
    stats = rate_limiter.get_stats()
    
    assert "active_ips" in stats
    assert "total_tracked_requests" in stats
    assert "whitelist_size" in stats
    assert "config" in stats
    assert stats["config"]["max_requests"] == 5
    assert stats["config"]["time_window"] == 10
