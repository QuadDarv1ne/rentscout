"""
Adaptive Rate Limiter для внешних API.

Автоматически регулирует скорость запросов на основе:
- Статус-кодов ответов (429, 403, 503)
- Времени ответа
- Частоты ошибок

Принцип работы:
- При получении 429/403/503 - увеличивает задержку
- При успешных запросах - постепенно уменьшает задержку
- Использует экспоненциальное backoff при ошибках
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum

from app.utils.logger import logger


class RateLimitState(str, Enum):
    """Состояния rate limiter."""
    NORMAL = "normal"           # Нормальная работа
    CAUTIOUS = "cautious"       # Увеличенная осторожность
    THROTTLED = "throttled"     # Существенное ограничение


@dataclass
class RateLimitConfig:
    """Конфигурация adaptive rate limiter."""
    base_delay: float = 1.0             # Базовая задержка (сек)
    min_delay: float = 0.5              # Минимальная задержка
    max_delay: float = 60.0             # Максимальная задержка
    increase_factor: float = 2.0        # Фактор увеличения при ошибке
    decrease_factor: float = 0.9        # Фактор уменьшения при успехе
    success_threshold: int = 10         # Успехов для уменьшения задержки
    error_threshold: int = 3            # Ошибок для увеличения задержки
    cooldown_window: float = 60.0       # Окно для подсчёта ошибок (сек)


@dataclass
class RateLimitStats:
    """Статистика rate limiter."""
    total_requests: int = 0
    successful_requests: int = 0
    rate_limited_requests: int = 0
    current_delay: float = 0.0
    state: RateLimitState = RateLimitState.NORMAL
    last_error_time: Optional[float] = None
    last_success_time: Optional[float] = None
    consecutive_errors: int = 0
    consecutive_successes: int = 0
    errors_in_window: int = 0


class AdaptiveRateLimiter:
    """
    Адаптивный rate limiter для внешних API.

    Пример использования:
        limiter = AdaptiveRateLimiter("avito")

        async with limiter:
            response = await client.get(url)
            await limiter.record_response(response.status_code)
    """

    _limiters: Dict[str, 'AdaptiveRateLimiter'] = {}
    _lock = asyncio.Lock()

    def __init__(
        self,
        service_name: str,
        config: Optional[RateLimitConfig] = None
    ):
        self.service_name = service_name
        self.config = config or RateLimitConfig()
        self.stats = RateLimitStats()
        self.stats.current_delay = self.config.base_delay
        self._error_timestamps: list[float] = []
        self._lock = asyncio.Lock()

    @classmethod
    async def get_limiter(
        cls,
        service_name: str,
        config: Optional[RateLimitConfig] = None
    ) -> 'AdaptiveRateLimiter':
        """Получить или создать limiter для сервиса."""
        async with cls._lock:
            if service_name not in cls._limiters:
                cls._limiters[service_name] = cls(service_name, config)
                logger.info(f"Created adaptive rate limiter for '{service_name}'")
            return cls._limiters[service_name]

    @classmethod
    def get_all_limiters(cls) -> Dict[str, 'AdaptiveRateLimiter']:
        """Получить все limiter'ы."""
        return cls._limiters.copy()

    async def acquire(self) -> float:
        """
        Получить задержку перед следующим запросом.

        Returns:
            Задержка в секундах
        """
        async with self._lock:
            delay = self.stats.current_delay

            if delay > self.config.base_delay:
                logger.debug(
                    f"Rate limiter '{self.service_name}': "
                    f"delaying {delay:.2f}s (state: {self.stats.state.value})"
                )

            if delay > 0:
                await asyncio.sleep(delay)

            return delay

    async def record_response(self, status_code: int, response_time: Optional[float] = None) -> None:
        """
        Записать результат запроса для адаптации задержки.

        Args:
            status_code: HTTP статус-код ответа
            response_time: Время ответа (сек)
        """
        async with self._lock:
            self.stats.total_requests += 1
            now = time.time()

            # Очистка старых ошибок из окна
            self._cleanup_error_window(now)

            if status_code in (429, 403, 503):
                # Rate limit или forbidden - увеличиваем задержку
                await self._on_rate_limit(now)
            elif status_code >= 500:
                # Server error - тоже увеличиваем, но менее агрессивно
                await self._on_server_error(now)
            elif status_code in (200, 201, 204):
                # Успех - уменьшаем задержку
                await self._on_success(now)
            else:
                # Другие статусы - логируем
                logger.debug(
                    f"Rate limiter '{self.service_name}': "
                    f"unexpected status code {status_code}"
                )

    async def _on_rate_limit(self, now: float) -> None:
        """Обработка rate limit (429, 403, 503)."""
        self.stats.rate_limited_requests += 1
        self.stats.consecutive_successes = 0
        self.stats.consecutive_errors += 1
        self.stats.last_error_time = now
        self.stats.errors_in_window += 1
        self._error_timestamps.append(now)

        # Увеличиваем задержку экспоненциально
        old_delay = self.stats.current_delay
        self.stats.current_delay = min(
            self.stats.current_delay * self.config.increase_factor,
            self.config.max_delay
        )

        # Обновляем состояние
        if self.stats.current_delay >= self.config.max_delay * 0.5:
            self.stats.state = RateLimitState.THROTTLED
        elif self.stats.current_delay > self.config.base_delay:
            self.stats.state = RateLimitState.CAUTIOUS

        logger.warning(
            f"Rate limiter '{self.service_name}': rate limit detected! "
            f"Delay increased: {old_delay:.2f}s → {self.stats.current_delay:.2f}s "
            f"(state: {self.stats.state.value})"
        )

    async def _on_server_error(self, now: float) -> None:
        """Обработка server error (5xx)."""
        self.stats.consecutive_successes = 0
        self.stats.consecutive_errors += 1
        self.stats.last_error_time = now
        self.stats.errors_in_window += 1
        self._error_timestamps.append(now)

        # Увеличиваем задержку, но менее агрессивно
        old_delay = self.stats.current_delay
        self.stats.current_delay = min(
            self.stats.current_delay * 1.5,
            self.config.max_delay
        )

        logger.debug(
            f"Rate limiter '{self.service_name}': server error. "
            f"Delay: {old_delay:.2f}s → {self.stats.current_delay:.2f}s"
        )

    async def _on_success(self, now: float) -> None:
        """Обработка успешного запроса."""
        self.stats.successful_requests += 1
        self.stats.consecutive_errors = 0
        self.stats.consecutive_successes += 1
        self.stats.last_success_time = now

        # Уменьшаем задержку после порога успехов
        if self.stats.consecutive_successes >= self.config.success_threshold:
            old_delay = self.stats.current_delay
            self.stats.current_delay = max(
                self.stats.current_delay * self.config.decrease_factor,
                self.config.min_delay
            )

            # Обновляем состояние
            if self.stats.current_delay <= self.config.base_delay:
                self.stats.state = RateLimitState.NORMAL
            elif self.stats.current_delay < self.config.base_delay * 2:
                self.stats.state = RateLimitState.CAUTIOUS

            # Сбрасываем счётчик успехов
            self.stats.consecutive_successes = 0

            if old_delay != self.stats.current_delay:
                logger.debug(
                    f"Rate limiter '{self.service_name}': delay decreased "
                    f"{old_delay:.2f}s → {self.stats.current_delay:.2f}s"
                )

    def _cleanup_error_window(self, now: float) -> None:
        """Очистить старые ошибки из окна."""
        cutoff = now - self.config.cooldown_window
        self._error_timestamps = [
            ts for ts in self._error_timestamps if ts > cutoff
        ]
        self.stats.errors_in_window = len(self._error_timestamps)

    def get_stats(self) -> dict:
        """Получить статистику limiter."""
        return {
            'service_name': self.service_name,
            'state': self.stats.state.value,
            'current_delay': self.stats.current_delay,
            'stats': {
                'total_requests': self.stats.total_requests,
                'successful_requests': self.stats.successful_requests,
                'rate_limited_requests': self.stats.rate_limited_requests,
                'consecutive_errors': self.stats.consecutive_errors,
                'consecutive_successes': self.stats.consecutive_successes,
                'errors_in_window': self.stats.errors_in_window,
            },
            'config': {
                'min_delay': self.config.min_delay,
                'max_delay': self.config.max_delay,
                'base_delay': self.config.base_delay,
            }
        }

    async def reset(self) -> None:
        """Сбросить limiter в начальное состояние."""
        async with self._lock:
            self.stats = RateLimitStats()
            self.stats.current_delay = self.config.base_delay
            self._error_timestamps = []
            logger.info(f"Rate limiter '{self.service_name}' reset to normal")

    async def __aenter__(self) -> 'AdaptiveRateLimiter':
        """Контекстный менеджер: acquire перед запросом."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Контекстный менеджер: ничего не делаем после запроса."""
        pass


# ============================================================================
# Декоратор для удобного использования
# ============================================================================

def adaptive_rate_limit(service_name: str):
    """
    Декоратор adaptive rate limiting.

    Пример:
        @adaptive_rate_limit("avito")
        async def fetch_avito_data():
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            limiter = await AdaptiveRateLimiter.get_limiter(service_name)

            async with limiter:
                result = await func(*args, **kwargs)
                return result

        return wrapper
    return decorator


# ============================================================================
# Экспорт
# ============================================================================

__all__ = [
    "AdaptiveRateLimiter",
    "AdaptiveRateLimiterConfig",
    "RateLimitConfig",
    "RateLimitState",
    "RateLimitStats",
    "adaptive_rate_limit",
]

# Alias для обратной совместимости
AdaptiveRateLimiterConfig = RateLimitConfig
