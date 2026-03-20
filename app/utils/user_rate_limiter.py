"""
Role-based Rate Limiting.

Rate limiting с учётом роли пользователя:
- user: 100 запросов/мин
- premium: 500 запросов/мин
- admin: 1000 запросов/мин
- moderator: 300 запросов/мин
"""

import time
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import asyncio

from app.core.config import settings
from app.core.security import UserRole
from app.utils.metrics import metrics_collector


# Лимиты для разных ролей
ROLE_LIMITS = {
    UserRole.USER: {"requests": 100, "window": 60},
    UserRole.MODERATOR: {"requests": 300, "window": 60},
    UserRole.PREMIUM: {"requests": 500, "window": 60},
    UserRole.ADMIN: {"requests": 1000, "window": 60},
}

# Лимиты для конкретных endpoints
ENDPOINT_LIMITS = {
    "/api/auth/login": {"requests": 5, "window": 60},  # 5 попыток входа в минуту
    "/api/auth/register": {"requests": 3, "window": 300},  # 3 регистрации в 5 минут
    "/api/auth/2fa/verify": {"requests": 5, "window": 60},  # 5 попыток 2FA
    "/api/properties/search": {"requests": 30, "window": 60},  # 30 поисков в минуту
    "/api/ml/predict": {"requests": 10, "window": 60},  # 10 предсказаний в минуту
}


class RoleBasedRateLimiter:
    """Rate limiter на основе роли пользователя."""

    def __init__(self):
        # Хранилище запросов: {user_id: [(timestamp, endpoint), ...]}
        self.user_requests: Dict[int, List[Tuple[float, str]]] = defaultdict(list)
        
        # Отдельно для IP (для неаутентифицированных)
        self.ip_requests: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
        
        self._lock = asyncio.Lock()

    def _get_role_limits(self, role: Optional[UserRole]) -> Dict[str, int]:
        """Получить лимиты для роли."""
        if role is None:
            # Для неаутентифицированных — минимальные лимиты
            return {"requests": 20, "window": 60}
        
        return ROLE_LIMITS.get(role, ROLE_LIMITS[UserRole.USER])

    def _get_endpoint_limit(self, endpoint: str) -> Optional[Dict[str, int]]:
        """Получить лимит для конкретного endpoint."""
        # Нормализуем endpoint (убираем query параметры и ID)
        normalized = endpoint.split("?")[0]
        
        # Проверяем точное совпадение
        if normalized in ENDPOINT_LIMITS:
            return ENDPOINT_LIMITS[normalized]
        
        # Проверяем паттерны (например, /api/auth/login-with-2fa)
        for pattern, limit in ENDPOINT_LIMITS.items():
            if normalized.startswith(pattern):
                return limit
        
        return None

    def _clean_old_requests(
        self, 
        requests_list: List[Tuple[float, str]], 
        now: float, 
        window: int
    ) -> List[Tuple[float, str]]:
        """Удаление старых запросов вне окна."""
        return [
            (req_time, endpoint)
            for req_time, endpoint in requests_list
            if now - req_time < window
        ]

    async def check_rate_limit(
        self,
        user_id: Optional[int] = None,
        role: Optional[UserRole] = None,
        endpoint: str = "/api/unknown",
        ip: str = "unknown"
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Проверка rate limit.

        Args:
            user_id: ID пользователя (если есть)
            role: Роль пользователя
            endpoint: Запрашиваемый endpoint
            ip: IP адрес (fallback)

        Returns:
            (is_allowed, rate_limit_info)
        """
        now = time.time()

        # Определяем ключ для лимитинга
        if user_id is not None:
            key = str(user_id)
            requests_dict = self.user_requests
        else:
            key = ip
            requests_dict = self.ip_requests

        # Получаем лимиты
        role_limits = self._get_role_limits(role)
        endpoint_limit = self._get_endpoint_limit(endpoint)

        # Используем более строгий лимит
        if endpoint_limit:
            max_requests = min(role_limits["requests"], endpoint_limit["requests"])
            window = min(role_limits["window"], endpoint_limit["window"])
        else:
            max_requests = role_limits["requests"]
            window = role_limits["window"]

        async with self._lock:
            # Очищаем старые запросы
            requests_dict[key] = self._clean_old_requests(
                requests_dict[key], 
                now, 
                window
            )

            current_requests = len(requests_dict[key])

            # Проверяем лимит
            if current_requests >= max_requests:
                # Находим самый старый запрос для расчёта retry_after
                if requests_dict[key]:
                    oldest_request = min(req_time for req_time, _ in requests_dict[key])
                    retry_after = int(window - (now - oldest_request) + 1)
                else:
                    retry_after = window

                # Записываем метрики
                metrics_collector.record_rate_limit_exceeded(key)

                return False, {
                    "error": "Rate limit exceeded",
                    "retry_after": max(1, retry_after),
                    "limit": max_requests,
                    "window": window,
                    "current": current_requests,
                    "role": role.value if role else "anonymous",
                }

            # Добавляем запрос
            requests_dict[key].append((now, endpoint))

            return True, {
                "remaining": max_requests - current_requests - 1,
                "limit": max_requests,
                "window": window,
                "role": role.value if role else "anonymous",
            }

    async def get_usage_stats(
        self,
        user_id: Optional[int] = None,
        ip: str = "unknown"
    ) -> Dict[str, any]:
        """Получить статистику использования."""
        now = time.time()
        
        # Определяем ключ
        if user_id is not None:
            key = str(user_id)
            requests_dict = self.user_requests
        else:
            key = ip
            requests_dict = self.ip_requests

        # Считаем запросы за разные периоды
        requests_dict[key] = self._clean_old_requests(requests_dict[key], now, 60)
        requests_last_minute = len(requests_dict[key])

        requests_dict[key] = self._clean_old_requests(requests_dict[key], now, 3600)
        requests_last_hour = len(requests_dict[key])

        return {
            "user_id": user_id,
            "ip": ip,
            "requests_last_minute": requests_last_minute,
            "requests_last_hour": requests_last_hour,
            "total_requests": sum(len(v) for v in requests_dict.values()),
        }

    async def reset_limits(self, user_id: Optional[int] = None):
        """Сбросить лимиты для пользователя."""
        if user_id is not None:
            self.user_requests[user_id] = []
        else:
            self.user_requests.clear()
            self.ip_requests.clear()


# Глобальный экземпляр
role_rate_limiter = RoleBasedRateLimiter()


__all__ = [
    "role_rate_limiter",
    "RoleBasedRateLimiter",
    "ROLE_LIMITS",
    "ENDPOINT_LIMITS",
]
