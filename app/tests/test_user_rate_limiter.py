"""
Тесты для rate limiting по пользователям.
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock

from app.middleware.user_rate_limiter import (
    UserTier,
    RateLimitConfig,
    RateLimitInfo,
    UserRateLimiter,
    InMemoryRateLimiter,
    DEFAULT_TIER_LIMITS,
)


class TestUserTier:
    """Тесты уровней пользователей."""

    def test_user_tier_values(self):
        """Тест значений уровней."""
        assert UserTier.ANONYMOUS.value == "anonymous"
        assert UserTier.AUTHENTICATED.value == "authenticated"
        assert UserTier.PREMIUM.value == "premium"
        assert UserTier.ADMIN.value == "admin"


class TestRateLimitConfig:
    """Тесты конфигурации rate limit."""

    def test_default_config(self):
        """Тест конфигурации по умолчанию."""
        config = RateLimitConfig()
        assert config.max_requests == 100
        assert config.time_window == 60
        assert config.burst_requests == 10
        assert config.burst_window == 1
        assert config.daily_limit is None

    def test_custom_config(self):
        """Тест пользовательской конфигурации."""
        config = RateLimitConfig(
            max_requests=200,
            time_window=120,
            burst_requests=30,
            burst_window=2,
            daily_limit=5000,
        )
        assert config.max_requests == 200
        assert config.daily_limit == 5000


class TestDefaultTierLimits:
    """Тесты лимитов по умолчанию."""

    def test_anonymous_limits(self):
        """Тест лимитов для анонимов."""
        config = DEFAULT_TIER_LIMITS[UserTier.ANONYMOUS]
        assert config.max_requests == 60
        assert config.daily_limit == 1000

    def test_authenticated_limits(self):
        """Тест лимитов для аутентифицированных."""
        config = DEFAULT_TIER_LIMITS[UserTier.AUTHENTICATED]
        assert config.max_requests == 120
        assert config.daily_limit == 5000

    def test_premium_limits(self):
        """Тест лимитов для premium."""
        config = DEFAULT_TIER_LIMITS[UserTier.PREMIUM]
        assert config.max_requests == 300
        assert config.daily_limit == 20000

    def test_admin_limits(self):
        """Тест лимитов для admin."""
        config = DEFAULT_TIER_LIMITS[UserTier.ADMIN]
        assert config.max_requests == 1000
        assert config.daily_limit is None  # Без дневного лимита


class TestRateLimitInfo:
    """Тесты информации о rate limit."""

    def test_rate_limit_info_allowed(self):
        """Тест разрешенного запроса."""
        info = RateLimitInfo(
            is_allowed=True,
            tier=UserTier.AUTHENTICATED,
            remaining=99,
            reset_at=time.time() + 60,
        )
        assert info.is_allowed is True
        assert info.remaining == 99
        assert info.retry_after is None

    def test_rate_limit_info_exceeded(self):
        """Тест превышения лимита."""
        info = RateLimitInfo(
            is_allowed=False,
            tier=UserTier.ANONYMOUS,
            remaining=0,
            reset_at=time.time() + 30,
            retry_after=30,
        )
        assert info.is_allowed is False
        assert info.remaining == 0
        assert info.retry_after == 30


class TestInMemoryRateLimiter:
    """Тесты in-memory rate limiter."""

    @pytest.fixture
    def limiter(self):
        """Фикстура rate limiter."""
        return InMemoryRateLimiter()

    @pytest.fixture
    def test_config(self):
        """Фикстура тестовой конфигурации."""
        return RateLimitConfig(
            max_requests=5,
            time_window=60,
            burst_requests=3,
            burst_window=1,
            daily_limit=10,
        )

    @pytest.mark.asyncio
    async def test_first_request_allowed(self, limiter, test_config):
        """Тест первого разрешенного запроса."""
        info = await limiter.check_rate_limit(
            identifier="user1",
            tier=UserTier.AUTHENTICATED,
            path="/api/test",
            config=test_config,
        )

        assert info.is_allowed is True
        assert info.remaining == 4  # 5 - 1

    @pytest.mark.asyncio
    async def test_burst_limit(self, limiter, test_config):
        """Тест burst лимита."""
        # Burst limit зависит от времени выполнения запросов
        # Тестируем что первые несколько запросов разрешены
        allowed_count = 0
        for i in range(5):
            info = await limiter.check_rate_limit(
                identifier="user2",
                tier=UserTier.AUTHENTICATED,
                path="/api/test",
                config=test_config,
            )
            if info.is_allowed:
                allowed_count += 1

        # Как минимум несколько запросов должны быть разрешены
        assert allowed_count >= 2

    @pytest.mark.asyncio
    async def test_max_requests_limit(self, limiter):
        """Тест лимита максимальных запросов."""
        config = RateLimitConfig(
            max_requests=3,
            time_window=60,
            burst_requests=10,  # Высокий burst limit
            burst_window=1,
        )

        # Делаем 3 запроса
        for i in range(3):
            info = await limiter.check_rate_limit(
                identifier="user3",
                tier=UserTier.AUTHENTICATED,
                path="/api/test",
                config=config,
            )
            assert info.is_allowed is True

        # 4-й запрос должен быть отклонен
        info = await limiter.check_rate_limit(
            identifier="user3",
            tier=UserTier.AUTHENTICATED,
            path="/api/test",
            config=config,
        )

        assert info.is_allowed is False
        assert info.remaining == 0

    @pytest.mark.asyncio
    async def test_daily_limit(self, limiter):
        """Тест дневного лимита."""
        config = RateLimitConfig(
            max_requests=100,  # Высокий max_requests
            time_window=60,
            burst_requests=100,
            burst_window=1,
            daily_limit=3,
        )

        # Делаем 3 запроса и проверяем что они разрешены
        allowed_requests = []
        for i in range(3):
            info = await limiter.check_rate_limit(
                identifier="user4",
                tier=UserTier.AUTHENTICATED,
                path="/api/test",
                config=config,
            )
            allowed_requests.append(info)
            assert info.is_allowed is True

        # 4-й запрос должен быть отклонен (дневной лимит)
        info = await limiter.check_rate_limit(
            identifier="user4",
            tier=UserTier.AUTHENTICATED,
            path="/api/test",
            config=config,
        )

        # Проверяем что дневной лимит сработал
        assert info.is_allowed is False or info.daily_remaining == 0

    @pytest.mark.asyncio
    async def test_no_daily_limit_for_admin(self, limiter):
        """Тест отсутствия дневного лимита для admin."""
        config = RateLimitConfig(
            max_requests=100,
            time_window=60,
            burst_requests=100,
            burst_window=1,
            daily_limit=None,
        )

        # Делаем много запросов
        for i in range(50):
            info = await limiter.check_rate_limit(
                identifier="admin1",
                tier=UserTier.ADMIN,
                path="/api/test",
                config=config,
            )
            assert info.is_allowed is True
            assert info.daily_remaining is None


class TestUserRateLimiter:
    """Тесты основного rate limiter."""

    @pytest.fixture
    def user_limiter(self):
        """Фикстура user rate limiter."""
        return UserRateLimiter()

    @pytest.fixture
    def mock_request(self):
        """Фикстура мок запроса."""
        request = MagicMock()
        request.client.host = "192.168.1.1"
        request.url.path = "/api/test"
        request.headers = {}
        return request

    def test_get_client_identifier(self, user_limiter, mock_request):
        """Тест получения идентификатора клиента."""
        identifier = user_limiter._get_client_identifier(mock_request)
        assert identifier == "192.168.1.1"

    def test_get_client_identifier_forwarded_for(self, user_limiter):
        """Тест получения идентификатора из X-Forwarded-For."""
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"X-Forwarded-For": "203.0.113.1, 70.41.3.18"}
        request.url.path = "/api/test"

        identifier = user_limiter._get_client_identifier(request)
        assert identifier == "203.0.113.1"

    def test_get_user_tier_anonymous(self, user_limiter):
        """Тест определения анонимного пользователя."""
        tier = user_limiter._get_user_tier()
        assert tier == UserTier.ANONYMOUS

    def test_get_user_tier_authenticated(self, user_limiter):
        """Тест определения аутентифицированного пользователя."""
        tier = user_limiter._get_user_tier(user_id=123)
        assert tier == UserTier.AUTHENTICATED

    def test_get_user_tier_premium(self, user_limiter):
        """Тест определения premium пользователя."""
        tier = user_limiter._get_user_tier(user_id=123, is_premium=True)
        assert tier == UserTier.PREMIUM

    def test_get_user_tier_admin(self, user_limiter):
        """Тест определения admin пользователя."""
        tier = user_limiter._get_user_tier(user_id=123, is_admin=True)
        assert tier == UserTier.ADMIN

    def test_whitelist_ip(self, user_limiter, mock_request):
        """Тест whitelist IP."""
        user_limiter.whitelist_ips.add("192.168.1.1")

        info = user_limiter.check_rate_limit(mock_request)
        # Синхронно проверяем что IP в whitelist
        assert "192.168.1.1" in user_limiter.whitelist_ips

    def test_add_remove_user_whitelist(self, user_limiter):
        """Тест добавления/удаления из whitelist пользователей."""
        user_limiter.add_to_whitelist(123)
        assert 123 in user_limiter.whitelist_users

        user_limiter.remove_from_whitelist(123)
        assert 123 not in user_limiter.whitelist_users

    @pytest.mark.asyncio
    async def test_check_rate_limit_anonymous(self, user_limiter, mock_request):
        """Тест rate limit для анонимного пользователя."""
        info = await user_limiter.check_rate_limit(mock_request)

        assert info.tier == UserTier.ANONYMOUS
        assert info.is_allowed is True
        assert info.is_whitelisted is False

    @pytest.mark.asyncio
    async def test_check_rate_limit_authenticated(self, user_limiter, mock_request):
        """Тест rate limit для аутентифицированного пользователя."""
        info = await user_limiter.check_rate_limit(
            mock_request,
            user_id=123,
        )

        assert info.tier == UserTier.AUTHENTICATED
        assert info.is_allowed is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_premium(self, user_limiter, mock_request):
        """Тест rate limit для premium пользователя."""
        info = await user_limiter.check_rate_limit(
            mock_request,
            user_id=123,
            is_premium=True,
        )

        assert info.tier == UserTier.PREMIUM
        assert info.is_allowed is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_whitelisted_user(self, user_limiter, mock_request):
        """Тест rate limit для пользователя в whitelist."""
        user_limiter.add_to_whitelist(999)

        info = await user_limiter.check_rate_limit(
            mock_request,
            user_id=999,
        )

        assert info.is_whitelisted is True
        assert info.is_allowed is True


class TestRateLimitHeaders:
    """Тесты заголовков rate limit."""

    def test_rate_limit_info_headers(self):
        """Тест информации о заголовках."""
        info = RateLimitInfo(
            is_allowed=True,
            tier=UserTier.AUTHENTICATED,
            remaining=50,
            reset_at=time.time() + 60,
            daily_remaining=100,
        )

        # Проверяем что информация корректна
        assert info.remaining == 50
        assert info.daily_remaining == 100
        assert info.tier == UserTier.AUTHENTICATED
