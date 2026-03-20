"""
Тесты для role-based rate limiting.
"""
import pytest
import asyncio
from app.utils.user_rate_limiter import (
    role_rate_limiter,
    RoleBasedRateLimiter,
    ROLE_LIMITS,
    ENDPOINT_LIMITS,
)
from app.core.security import UserRole


class TestRoleBasedRateLimiter:
    """Тесты для rate limiter с учётом ролей."""

    @pytest.mark.asyncio
    async def test_anonymous_user_limits(self):
        """Тест лимитов для анонимного пользователя."""
        limiter = RoleBasedRateLimiter()
        
        # 20 запросов для анонимных
        for i in range(20):
            is_allowed, info = await limiter.check_rate_limit(
                user_id=None,
                role=None,
                endpoint="/api/properties/search",
                ip="192.168.1.1"
            )
            assert is_allowed is True
        
        # 21-й запрос должен быть отклонён
        is_allowed, info = await limiter.check_rate_limit(
            user_id=None,
            role=None,
            endpoint="/api/properties/search",
            ip="192.168.1.1"
        )
        assert is_allowed is False
        assert info["error"] == "Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_user_role_limits(self):
        """Тест лимитов для обычного пользователя."""
        limiter = RoleBasedRateLimiter()
        
        # 100 запросов для user
        for i in range(100):
            is_allowed, info = await limiter.check_rate_limit(
                user_id=1,
                role=UserRole.USER,
                endpoint="/api/properties/search",
                ip="192.168.1.2"
            )
            assert is_allowed is True
        
        # 101-й запрос должен быть отклонён
        is_allowed, info = await limiter.check_rate_limit(
            user_id=1,
            role=UserRole.USER,
            endpoint="/api/properties/search",
            ip="192.168.1.2"
        )
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_admin_role_limits(self):
        """Тест лимитов для администратора."""
        limiter = RoleBasedRateLimiter()
        
        # 1000 запросов для admin
        for i in range(1000):
            is_allowed, info = await limiter.check_rate_limit(
                user_id=2,
                role=UserRole.ADMIN,
                endpoint="/api/properties/search",
                ip="192.168.1.3"
            )
            assert is_allowed is True
        
        # 1001-й запрос должен быть отклонён
        is_allowed, info = await limiter.check_rate_limit(
            user_id=2,
            role=UserRole.ADMIN,
            endpoint="/api/properties/search",
            ip="192.168.1.3"
        )
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_endpoint_specific_limits(self):
        """Тест специальных лимитов для endpoints."""
        limiter = RoleBasedRateLimiter()
        
        # /api/auth/login — только 5 попыток в минуту
        for i in range(5):
            is_allowed, info = await limiter.check_rate_limit(
                user_id=3,
                role=UserRole.ADMIN,  # Даже админ
                endpoint="/api/auth/login",
                ip="192.168.1.4"
            )
            assert is_allowed is True
        
        # 6-я попытка должна быть отклонена
        is_allowed, info = await limiter.check_rate_limit(
            user_id=3,
            role=UserRole.ADMIN,
            endpoint="/api/auth/login",
            ip="192.168.1.4"
        )
        assert is_allowed is False
        assert info["limit"] == 5  # Лимит endpoint'а

    @pytest.mark.asyncio
    async def test_different_users_independent(self):
        """Тест независимости лимитов разных пользователей."""
        limiter = RoleBasedRateLimiter()
        
        # Пользователь 1 делает 50 запросов
        for i in range(50):
            await limiter.check_rate_limit(
                user_id=10,
                role=UserRole.USER,
                endpoint="/api/properties/search",
                ip="192.168.1.5"
            )
        
        # Пользователь 2 должен иметь полный лимит
        is_allowed, info = await limiter.check_rate_limit(
            user_id=11,
            role=UserRole.USER,
            endpoint="/api/properties/search",
            ip="192.168.1.6"
        )
        assert is_allowed is True
        assert info["remaining"] == 99  # 100 - 1

    @pytest.mark.asyncio
    async def test_premium_role_limits(self):
        """Тест лимитов для premium пользователя."""
        limiter = RoleBasedRateLimiter()
        
        # 500 запросов для premium
        for i in range(500):
            is_allowed, info = await limiter.check_rate_limit(
                user_id=20,
                role=UserRole.PREMIUM,
                endpoint="/api/properties/search",
                ip="192.168.1.7"
            )
            assert is_allowed is True
        
        # 501-й запрос должен быть отклонён
        is_allowed, info = await limiter.check_rate_limit(
            user_id=20,
            role=UserRole.PREMIUM,
            endpoint="/api/properties/search",
            ip="192.168.1.7"
        )
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_moderator_role_limits(self):
        """Тест лимитов для модератора."""
        limiter = RoleBasedRateLimiter()
        
        # 300 запросов для moderator
        for i in range(300):
            is_allowed, info = await limiter.check_rate_limit(
                user_id=30,
                role=UserRole.MODERATOR,
                endpoint="/api/properties/search",
                ip="192.168.1.8"
            )
            assert is_allowed is True
        
        # 301-й запрос должен быть отклонён
        is_allowed, info = await limiter.check_rate_limit(
            user_id=30,
            role=UserRole.MODERATOR,
            endpoint="/api/properties/search",
            ip="192.168.1.8"
        )
        assert is_allowed is False

    @pytest.mark.asyncio
    async def test_rate_limit_info(self):
        """Тест информации о rate limit."""
        limiter = RoleBasedRateLimiter()
        
        is_allowed, info = await limiter.check_rate_limit(
            user_id=40,
            role=UserRole.USER,
            endpoint="/api/properties/search",
            ip="192.168.1.9"
        )
        
        assert is_allowed is True
        assert "remaining" in info
        assert "limit" in info
        assert "window" in info
        assert info["role"] == "user"
        assert info["limit"] == 100

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_info(self):
        """Тест информации о превышении лимита."""
        limiter = RoleBasedRateLimiter()
        
        # Исчерпываем лимит
        for i in range(21):  # 20 + 1 для анонима
            await limiter.check_rate_limit(
                user_id=None,
                role=None,
                endpoint="/api/properties/search",
                ip="192.168.1.10"
            )
        
        is_allowed, info = await limiter.check_rate_limit(
            user_id=None,
            role=None,
            endpoint="/api/properties/search",
            ip="192.168.1.10"
        )
        
        assert is_allowed is False
        assert "error" in info
        assert "retry_after" in info
        assert info["error"] == "Rate limit exceeded"
        assert info["retry_after"] > 0

    @pytest.mark.asyncio
    async def test_reset_limits(self):
        """Тест сброса лимитов."""
        limiter = RoleBasedRateLimiter()
        
        # Исчерпываем лимит
        for i in range(21):
            await limiter.check_rate_limit(
                user_id=50,
                role=UserRole.USER,
                endpoint="/api/properties/search",
                ip="192.168.1.11"
            )
        
        # Проверяем что лимит исчерпан
        is_allowed, info = await limiter.check_rate_limit(
            user_id=50,
            role=UserRole.USER,
            endpoint="/api/properties/search",
            ip="192.168.1.11"
        )
        assert is_allowed is False
        
        # Сбрасываем лимиты
        await limiter.reset_limits(user_id=50)
        
        # Теперь запрос должен пройти
        is_allowed, info = await limiter.check_rate_limit(
            user_id=50,
            role=UserRole.USER,
            endpoint="/api/properties/search",
            ip="192.168.1.11"
        )
        assert is_allowed is True

    @pytest.mark.asyncio
    async def test_get_usage_stats(self):
        """Тест статистики использования."""
        limiter = RoleBasedRateLimiter()
        
        # Делаем 10 запросов
        for i in range(10):
            await limiter.check_rate_limit(
                user_id=60,
                role=UserRole.USER,
                endpoint="/api/properties/search",
                ip="192.168.1.12"
            )
        
        stats = await limiter.get_usage_stats(user_id=60)
        
        assert stats["user_id"] == 60
        assert stats["requests_last_minute"] == 10
        assert stats["requests_last_hour"] == 10

    @pytest.mark.asyncio
    async def test_endpoint_limit_stricter_than_role(self):
        """Тест что лимит endpoint'а строже лимита роли."""
        limiter = RoleBasedRateLimiter()
        
        # Admin имеет 1000 запросов/мин, но /api/auth/login только 5
        for i in range(5):
            is_allowed, _ = await limiter.check_rate_limit(
                user_id=70,
                role=UserRole.ADMIN,
                endpoint="/api/auth/login",
                ip="192.168.1.13"
            )
            assert is_allowed is True
        
        # 6-й запрос должен быть отклонён несмотря на admin роль
        is_allowed, info = await limiter.check_rate_limit(
            user_id=70,
            role=UserRole.ADMIN,
            endpoint="/api/auth/login",
            ip="192.168.1.13"
        )
        assert is_allowed is False
        assert info["limit"] == 5  # Лимит endpoint'а, не роли


class TestRoleLimitsConfiguration:
    """Тесты конфигурации лимитов."""

    def test_role_limits_positive(self):
        """Тест что все лимиты ролей положительные."""
        for role, limits in ROLE_LIMITS.items():
            assert limits["requests"] > 0
            assert limits["window"] > 0

    def test_endpoint_limits_positive(self):
        """Тест что все лимиты endpoints положительные."""
        for endpoint, limits in ENDPOINT_LIMITS.items():
            assert limits["requests"] > 0
            assert limits["window"] > 0

    def test_admin_has_highest_limits(self):
        """Тест что у админа самые высокие лимиты."""
        admin_limits = ROLE_LIMITS[UserRole.ADMIN]["requests"]
        
        for role, limits in ROLE_LIMITS.items():
            if role != UserRole.ADMIN:
                assert limits["requests"] <= admin_limits


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
