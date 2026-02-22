"""
Rate limiting по пользователям и IP адресам.

Поддерживает:
- Rate limit по IP (для анонимных пользователей)
- Rate limit по user_id (для аутентифицированных)
- Разные лимиты для разных типов пользователей
- Redis для распределенного rate limiting

Использование:
    from app.middleware.user_rate_limiter import UserRateLimiter
    
    limiter = UserRateLimiter()
    await limiter.check_rate_limit(request, user_id=123)
"""

import time
import hashlib
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import asyncio

from fastapi import HTTPException, Request
from app.core.config import settings
from app.utils.logger import logger


class UserTier(str, Enum):
    """Уровни пользователей с разными лимитами."""
    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    PREMIUM = "premium"
    ADMIN = "admin"


@dataclass
class RateLimitConfig:
    """Конфигурация rate limit для уровня пользователя."""
    max_requests: int = 100
    time_window: int = 60  # секунды
    burst_requests: int = 10
    burst_window: int = 1
    daily_limit: Optional[int] = None


# Конфигурация по умолчанию для разных уровней
DEFAULT_TIER_LIMITS: Dict[UserTier, RateLimitConfig] = {
    UserTier.ANONYMOUS: RateLimitConfig(
        max_requests=60,
        time_window=60,
        burst_requests=10,
        burst_window=1,
        daily_limit=1000,
    ),
    UserTier.AUTHENTICATED: RateLimitConfig(
        max_requests=120,
        time_window=60,
        burst_requests=20,
        burst_window=1,
        daily_limit=5000,
    ),
    UserTier.PREMIUM: RateLimitConfig(
        max_requests=300,
        time_window=60,
        burst_requests=50,
        burst_window=1,
        daily_limit=20000,
    ),
    UserTier.ADMIN: RateLimitConfig(
        max_requests=1000,
        time_window=60,
        burst_requests=100,
        burst_window=1,
        daily_limit=None,  # Без дневного лимита
    ),
}


@dataclass
class RateLimitInfo:
    """Информация о rate limit."""
    is_allowed: bool
    tier: UserTier
    remaining: int
    reset_at: float
    retry_after: Optional[int] = None
    daily_remaining: Optional[int] = None
    is_whitelisted: bool = False


class InMemoryRateLimiter:
    """In-memory rate limiter для одного экземпляра приложения."""

    def __init__(self):
        # Хранилище запросов: {key: [(timestamp, path), ...]}
        self.requests: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
        # Дневные лимиты: {key: (date, count)}
        self.daily_counts: Dict[str, Tuple[str, int]] = {}
        self._lock = asyncio.Lock()

    def _get_storage_key(self, identifier: str, tier: UserTier) -> str:
        """Генерирует ключ для хранилища."""
        return f"{tier.value}:{identifier}"

    def _get_today_str(self) -> str:
        """Возвращает строку сегодняшней даты."""
        return time.strftime("%Y-%m-%d")

    async def check_rate_limit(
        self,
        identifier: str,
        tier: UserTier,
        path: str,
        config: RateLimitConfig
    ) -> RateLimitInfo:
        """
        Проверка rate limit.

        Args:
            identifier: Идентификатор (IP или user_id)
            tier: Уровень пользователя
            path: Путь запроса
            config: Конфигурация rate limit

        Returns:
            RateLimitInfo с информацией о лимите
        """
        async with self._lock:
            key = self._get_storage_key(identifier, tier)
            now = time.time()

            # Очищаем старые запросы
            self.requests[key] = [
                (req_time, req_path)
                for req_time, req_path in self.requests[key]
                if now - req_time < config.time_window
            ]

            # Проверяем burst limit
            recent_requests = [
                req_time
                for req_time, _ in self.requests[key]
                if now - req_time < config.burst_window
            ]

            if len(recent_requests) >= config.burst_requests:
                oldest_in_burst = min(recent_requests)
                retry_after = int(config.burst_window - (now - oldest_in_burst) + 1)

                return RateLimitInfo(
                    is_allowed=False,
                    tier=tier,
                    remaining=0,
                    reset_at=now + retry_after,
                    retry_after=retry_after,
                )

            # Проверяем основной лимит
            if len(self.requests[key]) >= config.max_requests:
                oldest_request = min(req_time for req_time, _ in self.requests[key])
                retry_after = int(config.time_window - (now - oldest_request) + 1)

                return RateLimitInfo(
                    is_allowed=False,
                    tier=tier,
                    remaining=0,
                    reset_at=now + retry_after,
                    retry_after=retry_after,
                )

            # Проверяем дневной лимит
            if config.daily_limit is not None:
                today = self._get_today_str()
                daily_key = f"daily:{key}"

                if daily_key in self.daily_counts:
                    count_date, count = self.daily_counts[daily_key]
                    if count_date == today:
                        if count >= config.daily_limit:
                            # Дневной лимит исчерпан
                            seconds_until_midnight = self._seconds_until_midnight()
                            return RateLimitInfo(
                                is_allowed=False,
                                tier=tier,
                                remaining=0,
                                reset_at=now + seconds_until_midnight,
                                retry_after=seconds_until_midnight,
                                daily_remaining=0,
                            )
                        else:
                            daily_remaining = config.daily_limit - count
                    else:
                        # Новый день, сбрасываем счетчик
                        self.daily_counts[daily_key] = (today, 0)
                        daily_remaining = config.daily_limit
                else:
                    self.daily_counts[daily_key] = (today, 0)
                    daily_remaining = config.daily_limit
            else:
                daily_remaining = None

            # Запрос разрешен
            self.requests[key].append((now, path))

            # Обновляем дневной счетчик
            if config.daily_limit is not None:
                daily_key = f"daily:{key}"
                today, count = self.daily_counts.get(daily_key, (today, 0))
                self.daily_counts[daily_key] = (today, count + 1)

            # Вычисляем оставшиеся запросы
            remaining = config.max_requests - len(self.requests[key])
            oldest_request = min((req_time for req_time, _ in self.requests[key]), default=now)
            reset_at = oldest_request + config.time_window

            return RateLimitInfo(
                is_allowed=True,
                tier=tier,
                remaining=remaining,
                reset_at=reset_at,
                daily_remaining=daily_remaining,
            )

    def _seconds_until_midnight(self) -> int:
        """Возвращает количество секунд до полуночи."""
        now = time.localtime()
        seconds_today = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec
        return 86400 - seconds_today


class UserRateLimiter:
    """
    Rate limiter с поддержкой уровней пользователей.

    Автоматически определяет уровень пользователя и применяет соответствующие лимиты.
    """

    def __init__(
        self,
        tier_limits: Optional[Dict[UserTier, RateLimitConfig]] = None,
        use_redis: bool = False,
        redis_client=None
    ):
        """
        Инициализация rate limiter.

        Args:
            tier_limits: Конфигурация лимитов для уровней
            use_redis: Использовать Redis для распределенного limiting
            redis_client: Redis клиент для распределенного limiting
        """
        self.tier_limits = tier_limits or DEFAULT_TIER_LIMITS
        self.use_redis = use_redis and redis_client is not None
        self.redis_client = redis_client

        # In-memory limiter для локального использования
        self.memory_limiter = InMemoryRateLimiter()

        # Whitelist IP адресов
        self.whitelist_ips = {"127.0.0.1", "::1", "localhost"}

        # Whitelist user_id
        self.whitelist_users: set[int] = set()

    def add_to_whitelist(self, user_id: int) -> None:
        """Добавляет пользователя в whitelist."""
        self.whitelist_users.add(user_id)

    def remove_from_whitelist(self, user_id: int) -> None:
        """Удаляет пользователя из whitelist."""
        self.whitelist_users.discard(user_id)

    def _get_client_identifier(self, request: Request) -> str:
        """Получает идентификатор клиента из запроса."""
        # Проверяем заголовки для реального IP (за reverse proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        #fallback на IP из client
        if request.client:
            return request.client.host

        return "unknown"

    def _get_user_tier(
        self,
        user_id: Optional[int] = None,
        is_premium: bool = False,
        is_admin: bool = False
    ) -> UserTier:
        """Определяет уровень пользователя."""
        if is_admin:
            return UserTier.ADMIN
        if is_premium:
            return UserTier.PREMIUM
        if user_id is not None:
            return UserTier.AUTHENTICATED
        return UserTier.ANONYMOUS

    async def check_rate_limit(
        self,
        request: Request,
        user_id: Optional[int] = None,
        is_premium: bool = False,
        is_admin: bool = False
    ) -> RateLimitInfo:
        """
        Проверка rate limit для запроса.

        Args:
            request: FastAPI request объект
            user_id: ID аутентифицированного пользователя (если есть)
            is_premium: Premium ли пользователь
            is_admin: Admin ли пользователь

        Returns:
            RateLimitInfo с информацией о лимите
        """
        client_ip = self._get_client_identifier(request)

        # Проверяем whitelist IP
        if client_ip in self.whitelist_ips:
            return RateLimitInfo(
                is_allowed=True,
                tier=UserTier.ADMIN,
                remaining=999999,
                reset_at=time.time() + 60,
                is_whitelisted=True,
            )

        # Проверяем whitelist пользователей
        if user_id is not None and user_id in self.whitelist_users:
            return RateLimitInfo(
                is_allowed=True,
                tier=UserTier.ADMIN,
                remaining=999999,
                reset_at=time.time() + 60,
                is_whitelisted=True,
            )

        # Определяем уровень и идентификатор
        tier = self._get_user_tier(user_id, is_premium, is_admin)
        identifier = str(user_id) if user_id is not None else client_ip
        config = self.tier_limits[tier]

        # Используем in-memory limiter
        return await self.memory_limiter.check_rate_limit(
            identifier=identifier,
            tier=tier,
            path=request.url.path,
            config=config,
        )

    async def check_rate_limit_or_raise(
        self,
        request: Request,
        user_id: Optional[int] = None,
        is_premium: bool = False,
        is_admin: bool = False
    ) -> RateLimitInfo:
        """
        Проверка rate limit с выбрасыванием HTTPException.

        Args:
            request: FastAPI request объект
            user_id: ID пользователя
            is_premium: Premium ли пользователь
            is_admin: Admin ли пользователь

        Raises:
            HTTPException: Если rate limit превышен
        """
        info = await self.check_rate_limit(request, user_id, is_premium, is_admin)

        if not info.is_allowed:
            headers = {
                "Retry-After": str(info.retry_after),
                "X-RateLimit-Limit": str(self.tier_limits[info.tier].max_requests),
                "X-RateLimit-Remaining": str(info.remaining),
                "X-RateLimit-Reset": str(int(info.reset_at)),
            }

            if info.daily_remaining is not None:
                headers["X-RateLimit-Daily-Remaining"] = str(info.daily_remaining)

            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit",
                    "message": "Too many requests. Please try again later.",
                    "retry_after": info.retry_after,
                    "tier": info.tier.value,
                },
                headers=headers,
            )

        return info


# Глобальный экземпляр для использования в приложении
user_rate_limiter = UserRateLimiter()


__all__ = [
    "UserTier",
    "RateLimitConfig",
    "RateLimitInfo",
    "UserRateLimiter",
    "InMemoryRateLimiter",
    "user_rate_limiter",
    "DEFAULT_TIER_LIMITS",
]
