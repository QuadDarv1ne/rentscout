"""
Специальный rate limiter для auth endpoints с защитой от brute-force.
"""

from typing import Dict, List, Tuple
import time
from collections import defaultdict

from app.core.config import settings
from app.utils.structured_logger import logger
from app.utils.metrics import metrics_collector


class AuthRateLimiter:
    """
    Rate limiter специально для auth endpoints.

    Более строгий чем общий IP rate limiter:
    - 5 попыток входа в минуту
    - 10 попыток регистрации в минуту
    - Отдельный лимит на refresh токены
    """

    def __init__(
        self,
        login_max_attempts: int = 5,
        login_window: int = 60,
        register_max_attempts: int = 10,
        register_window: int = 60,
        refresh_max_attempts: int = 10,
        refresh_window: int = 60,
    ):
        """
        Инициализация auth rate limiter.

        Args:
            login_max_attempts: Максимум попыток входа в окно
            login_window: Окно для login в секундах
            register_max_attempts: Максимум попыток регистрации
            register_window: Окно для регистрации
            refresh_max_attempts: Максимум refresh попыток
            refresh_window: Окно для refresh
        """
        self.login_max_attempts = login_max_attempts
        self.login_window = login_window
        self.register_max_attempts = register_max_attempts
        self.register_window = register_window
        self.refresh_max_attempts = refresh_max_attempts
        self.refresh_window = refresh_window

        # Хранилища для разных типов операций
        self.login_attempts: Dict[str, List[float]] = defaultdict(list)
        self.register_attempts: Dict[str, List[float]] = defaultdict(list)
        self.refresh_attempts: Dict[str, List[float]] = defaultdict(list)

        # Блокировки по IP (временные)
        self.banned_ips: Dict[str, float] = {}  # IP -> timestamp окончания блокировки

        # Whitelist
        self.whitelist = {"127.0.0.1", "::1", "localhost"}

    def _clean_old_attempts(self, attempts: List[float], window: float, now: float) -> List[float]:
        """Удаление старых попыток вне окна."""
        return [t for t in attempts if now - t < window]

    def _is_banned(self, ip: str, now: float) -> bool:
        """Проверка находится ли IP в бане."""
        if ip in self.banned_ips:
            if now < self.banned_ips[ip]:
                return True
            else:
                # Блокировка истекла
                del self.banned_ips[ip]
        return False

    def _ban_ip(self, ip: str, duration: int = 300):
        """
        Заблокировать IP.

        Args:
            ip: IP адрес для блокировки
            duration: Длительность блокировки в секундах (по умолчанию 5 минут)
        """
        now = time.time()
        self.banned_ips[ip] = now + duration
        logger.warning(
            f"IP забанен за чрезмерные попытки аутентификации",
            extra_data={"ip": ip, "duration": duration, "until": self.banned_ips[ip]},
        )

    async def check_login_attempt(self, ip: str, username: str = None) -> Tuple[bool, Dict]:
        """
        Проверка попытки входа.

        Args:
            ip: IP адрес клиента
            username: Имя пользователя (для логирования)

        Returns:
            (is_allowed, info)
        """
        # Whitelist пропускаем
        if ip in self.whitelist:
            return True, {"whitelisted": True}

        now = time.time()

        # Проверяем бан
        if self._is_banned(ip, now):
            retry_after = int(self.banned_ips[ip] - now)
            metrics_collector.record_rate_limit_exceeded(ip)
            return False, {
                "error": "IP временно заблокирован за чрезмерные попытки входа",
                "retry_after": retry_after,
                "banned": True,
            }

        # Очищаем старые попытки
        self.login_attempts[ip] = self._clean_old_attempts(
            self.login_attempts[ip],
            self.login_window,
            now
        )

        # Проверяем лимит
        if len(self.login_attempts[ip]) >= self.login_max_attempts:
            # Превышен лимит - бан на 5 минут
            self._ban_ip(ip, duration=300)

            metrics_collector.record_rate_limit_exceeded(ip)

            return False, {
                "error": "Превышено максимальное количество попыток входа",
                "retry_after": self.login_window,
                "limit": self.login_max_attempts,
                "window": self.login_window,
                "banned": True,
            }

        # Записываем попытку
        self.login_attempts[ip].append(now)

        # Логируем подозрительные активности (3+ неудачных попытки)
        if len(self.login_attempts[ip]) >= 3:
            logger.warning(
                f"Множественные попытки входа с IP",
                extra_data={
                    "ip": ip,
                    "username": username,
                    "attempt_count": len(self.login_attempts[ip]),
                },
            )

        remaining = self.login_max_attempts - len(self.login_attempts[ip])

        return True, {
            "limit": self.login_max_attempts,
            "remaining": remaining,
            "reset": int(now + self.login_window),
        }

    async def check_register_attempt(self, ip: str) -> Tuple[bool, Dict]:
        """
        Проверка попытки регистрации.

        Args:
            ip: IP адрес клиента

        Returns:
            (is_allowed, info)
        """
        if ip in self.whitelist:
            return True, {"whitelisted": True}

        now = time.time()

        if self._is_banned(ip, now):
            retry_after = int(self.banned_ips[ip] - now)
            return False, {
                "error": "IP временно заблокирован",
                "retry_after": retry_after,
                "banned": True,
            }

        self.register_attempts[ip] = self._clean_old_attempts(
            self.register_attempts[ip],
            self.register_window,
            now
        )

        if len(self.register_attempts[ip]) >= self.register_max_attempts:
            self._ban_ip(ip, duration=600)  # Бан на 10 минут

            metrics_collector.record_rate_limit_exceeded(ip)

            return False, {
                "error": "Превышено максимальное количество попыток регистрации",
                "retry_after": self.register_window,
                "limit": self.register_max_attempts,
                "banned": True,
            }

        self.register_attempts[ip].append(now)

        remaining = self.register_max_attempts - len(self.register_attempts[ip])

        return True, {
            "limit": self.register_max_attempts,
            "remaining": remaining,
            "reset": int(now + self.register_window),
        }

    async def check_refresh_attempt(self, ip: str) -> Tuple[bool, Dict]:
        """
        Проверка попытки обновления токена.

        Args:
            ip: IP адрес клиента

        Returns:
            (is_allowed, info)
        """
        if ip in self.whitelist:
            return True, {"whitelisted": True}

        now = time.time()

        if self._is_banned(ip, now):
            retry_after = int(self.banned_ips[ip] - now)
            return False, {
                "error": "IP временно заблокирован",
                "retry_after": retry_after,
                "banned": True,
            }

        self.refresh_attempts[ip] = self._clean_old_attempts(
            self.refresh_attempts[ip],
            self.refresh_window,
            now
        )

        if len(self.refresh_attempts[ip]) >= self.refresh_max_attempts:
            self._ban_ip(ip, duration=300)

            metrics_collector.record_rate_limit_exceeded(ip)

            return False, {
                "error": "Превышено максимальное количество попыток обновления токена",
                "retry_after": self.refresh_window,
                "limit": self.refresh_max_attempts,
                "banned": True,
            }

        self.refresh_attempts[ip].append(now)

        remaining = self.refresh_max_attempts - len(self.refresh_attempts[ip])

        return True, {
            "limit": self.refresh_max_attempts,
            "remaining": remaining,
            "reset": int(now + self.refresh_window),
        }

    def reset(self, ip: str):
        """Сброс всех лимитов для IP."""
        self.login_attempts.pop(ip, None)
        self.register_attempts.pop(ip, None)
        self.refresh_attempts.pop(ip, None)
        self.banned_ips.pop(ip, None)

    def get_stats(self) -> Dict:
        """Получение статистики."""
        now = time.time()

        active_login_ips = sum(
            1 for ip, attempts in self.login_attempts.items()
            if self._clean_old_attempts(attempts, self.login_window, now)
        )

        active_register_ips = sum(
            1 for ip, attempts in self.register_attempts.items()
            if self._clean_old_attempts(attempts, self.register_window, now)
        )

        return {
            "active_login_ips": active_login_ips,
            "active_register_ips": active_register_ips,
            "banned_ips": len(self.banned_ips),
            "config": {
                "login_max_attempts": self.login_max_attempts,
                "login_window": self.login_window,
                "register_max_attempts": self.register_max_attempts,
                "register_window": self.register_window,
                "refresh_max_attempts": self.refresh_max_attempts,
                "refresh_window": self.refresh_window,
            },
        }


# Глобальный экземпляр
auth_rate_limiter = AuthRateLimiter(
    login_max_attempts=5,  # 5 попыток входа в минуту
    login_window=60,
    register_max_attempts=10,  # 10 регистраций в минуту
    register_window=60,
    refresh_max_attempts=10,  # 10 refresh в минуту
    refresh_window=60,
)
