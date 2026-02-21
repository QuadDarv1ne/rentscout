"""
Расширенная обработка ошибок для парсеров.

Включает:
- Exponential backoff retry
- Fallback на кеш при ошибках
- Graceful degradation
- Alerting при критических ошибках
"""

import asyncio
import time
from typing import Optional, Callable, Any, Awaitable, TypeVar, List
from dataclasses import dataclass, field
from enum import Enum
import logging

from app.utils.logger import logger
from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorSeverity(str, Enum):
    """Уровни серьёзности ошибок."""
    LOW = "low"  # Не влияет на работу
    MEDIUM = "medium"  # Частичная деградация
    HIGH = "high"  # Серьёзная проблема
    CRITICAL = "critical"  # Полный отказ


@dataclass
class RetryConfig:
    """Конфигурация retry."""
    max_retries: int = 3
    base_delay: float = 1.0  # Базовая задержка (сек)
    max_delay: float = 60.0  # Максимальная задержка
    exponential_base: float = 2.0  # База экспоненты
    jitter: bool = True  # Добавить случайность
    retry_exceptions: tuple = (Exception,)  # Исключения для retry


@dataclass
class FallbackConfig:
    """Конфигурация fallback."""
    enabled: bool = True
    cache_fallback: bool = True  # Использовать кеш при ошибке
    default_value: Any = None  # Значение по умолчанию
    fallback_on_exceptions: tuple = (Exception,)


@dataclass
class ErrorStats:
    """Статистика ошибок."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    retry_attempts: int = 0
    fallback_used: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[float] = None
    consecutive_failures: int = 0
    errors_by_type: dict = field(default_factory=dict)


class MaxRetriesExceeded(Exception):
    """Превышено максимальное количество попыток."""
    def __init__(self, func_name: str, retries: int, last_error: Exception):
        self.func_name = func_name
        self.retries = retries
        self.last_error = last_error
        super().__init__(
            f"Function '{func_name}' failed after {retries} retries. "
            f"Last error: {str(last_error)}"
        )


class FallbackError(Exception):
    """Ошибка fallback."""
    pass


def calculate_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
) -> float:
    """
    Рассчитать задержку перед retry с exponential backoff.

    Args:
        attempt: Номер попытки (0-based)
        base_delay: Базовая задержка
        max_delay: Максимальная задержка
        exponential_base: База экспоненты
        jitter: Добавить случайность

    Returns:
        Задержка в секундах
    """
    import random

    # Exponential backoff: delay = base * (2 ^ attempt)
    delay = base_delay * (exponential_base ** attempt)

    # Добавляем jitter (±25%)
    if jitter:
        jitter_factor = 0.75 + random.random() * 0.5  # 0.75 - 1.25
        delay *= jitter_factor

    return min(delay, max_delay)


async def retry_with_backoff(
    func: Callable[..., Awaitable[T]],
    *args,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], Any]] = None,
    **kwargs
) -> T:
    """
    Вызвать функцию с retry и exponential backoff.

    Args:
        func: Асинхронная функция для вызова
        *args, **kwargs: Аргументы функции
        config: Конфигурация retry
        on_retry: Callback при retry (attempt, error, delay)

    Returns:
        Результат функции

    Raises:
        MaxRetriesExceeded: Если все попытки исчерпаны
    """
    config = config or RetryConfig()

    last_exception: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except config.retry_exceptions as e:
            last_exception = e

            if attempt < config.max_retries:
                # Рассчитать задержку
                delay = calculate_delay(
                    attempt,
                    config.base_delay,
                    config.max_delay,
                    config.exponential_base,
                    config.jitter
                )

                logger.warning(
                    f"Retry attempt {attempt + 1}/{config.max_retries} after {delay:.2f}s. "
                    f"Error: {type(e).__name__}: {str(e)}"
                )

                # Callback перед retry
                if on_retry:
                    on_retry(attempt, e, delay)

                # Ждём перед следующей попыткой
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {config.max_retries + 1} attempts failed for '{func.__name__}'. "
                    f"Last error: {str(e)}"
                )

    raise MaxRetriesExceeded(func.__name__, config.max_retries + 1, last_exception)  # type: ignore


async def with_fallback(
    func: Callable[..., Awaitable[T]],
    *args,
    fallback: Optional[Callable[..., Awaitable[T]]] = None,
    config: Optional[FallbackConfig] = None,
    **kwargs
) -> T:
    """
    Вызвать функцию с fallback при ошибке.

    Args:
        func: Основная функция
        *args, **kwargs: Аргументы
        fallback: Fallback функция
        config: Конфигурация fallback

    Returns:
        Результат основной или fallback функции
    """
    config = config or FallbackConfig()

    try:
        return await func(*args, **kwargs)

    except config.fallback_on_exceptions as e:
        logger.warning(
            f"Primary function failed, using fallback. Error: {type(e).__name__}: {str(e)}"
        )

        if fallback:
            try:
                return await fallback(*args, **kwargs)
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                if config.default_value is not None:
                    return config.default_value
                raise FallbackError(f"Both primary and fallback failed: {fallback_error}")

        elif config.default_value is not None:
            return config.default_value

        raise FallbackError(f"Primary function failed and no fallback configured: {e}")


class ResilientParser:
    """
    Обёртка для парсеров с retry, fallback и circuit breaker.

    Пример использования:
        parser = ResilientParser(AvitoParser())
        results = await parser.parse("Москва")
    """

    def __init__(
        self,
        parser,
        retry_config: Optional[RetryConfig] = None,
        fallback_config: Optional[FallbackConfig] = None,
        cache_manager=None
    ):
        self.parser = parser
        self.parser_name = parser.__class__.__name__
        self.retry_config = retry_config or RetryConfig(
            max_retries=getattr(settings, 'MAX_RETRIES', 3),
            base_delay=getattr(settings, 'RETRY_DELAY', 1.0),
        )
        self.fallback_config = fallback_config or FallbackConfig(
            enabled=getattr(settings, 'ENABLE_ADVANCED_CACHE', True),
            cache_fallback=True,
        )
        self.cache_manager = cache_manager
        self.stats = ErrorStats()

    async def parse(
        self,
        city: str,
        property_type: str = "Квартира",
        use_cache: bool = True
    ) -> List:
        """
        Парсинг с retry, fallback и кэшированием.

        Args:
            city: Город
            property_type: Тип недвижимости
            use_cache: Использовать кеш

        Returns:
            Список свойств
        """
        self.stats.total_calls += 1
        cache_key = f"parser:{self.parser_name}:{city}:{property_type}"

        async def do_parse():
            return await self.parser.parse(city, property_type)

        async def cache_fallback():
            if self.cache_manager and use_cache:
                logger.info(f"Using cache fallback for {cache_key}")
                self.stats.fallback_used += 1
                return await self.cache_manager.get(cache_key) or []
            return []

        try:
            # Retry с exponential backoff
            result = await retry_with_backoff(
                do_parse,
                config=self.retry_config,
                on_retry=lambda attempt, error, delay: setattr(self.stats, 'retry_attempts', self.stats.retry_attempts + 1)
            )

            self.stats.successful_calls += 1
            self.stats.consecutive_failures = 0

            # Кэшируем успешный результат
            if self.cache_manager and result:
                await self.cache_manager.set(cache_key, result, ttl=3600)

            return result

        except MaxRetriesExceeded as e:
            self.stats.failed_calls += 1
            self.stats.consecutive_failures += 1
            self.stats.last_error = str(e)
            self.stats.last_error_time = time.time()

            logger.error(f"Parser {self.parser_name} failed after all retries: {e}")

            # Fallback на кеш
            if self.fallback_config.enabled and self.fallback_config.cache_fallback:
                return await cache_fallback()

            return []

        except Exception as e:
            self.stats.failed_calls += 1
            self.stats.consecutive_failures += 1
            self.stats.last_error = f"{type(e).__name__}: {str(e)}"
            self.stats.last_error_time = time.time()

            # Классификация ошибки
            error_type = type(e).__name__
            self.stats.errors_by_type[error_type] = self.stats.errors_by_type.get(error_type, 0) + 1

            logger.error(f"Parser {self.parser_name} unexpected error: {e}")

            # Fallback
            if self.fallback_config.enabled:
                return await cache_fallback()

            return []

    def get_stats(self) -> dict:
        """Получить статистику парсера."""
        return {
            'parser_name': self.parser_name,
            'total_calls': self.stats.total_calls,
            'successful_calls': self.stats.successful_calls,
            'failed_calls': self.stats.failed_calls,
            'retry_attempts': self.stats.retry_attempts,
            'fallback_used': self.stats.fallback_used,
            'consecutive_failures': self.stats.consecutive_failures,
            'last_error': self.stats.last_error,
            'errors_by_type': self.stats.errors_by_type,
        }


class AlertManager:
    """
    Менеджер алертов для критических ошибок.

    Отправляет уведомления при:
    - Превышении порога ошибок
    - Полном отказе парсера
    - Series consecutive failures
    """

    def __init__(
        self,
        error_threshold: int = 10,
        consecutive_failure_threshold: int = 5,
        alert_cooldown: int = 300  # 5 минут между алертами
    ):
        self.error_threshold = error_threshold
        self.consecutive_failure_threshold = consecutive_failure_threshold
        self.alert_cooldown = alert_cooldown
        self._last_alert_time: dict[str, float] = {}
        self._error_counts: dict[str, int] = {}

    async def check_and_alert(
        self,
        parser_name: str,
        stats: ErrorStats,
        alert_callback: Optional[Callable[[str, str], Awaitable[None]]] = None
    ) -> bool:
        """
        Проверить метрики и отправить алерт если нужно.

        Args:
            parser_name: Название парсера
            stats: Статистика ошибок
            alert_callback: Функция для отправки алерта (title, message)

        Returns:
            True если алерт отправлен
        """
        should_alert = False
        alert_reason = ""

        # Проверка consecutive failures
        if stats.consecutive_failures >= self.consecutive_failure_threshold:
            should_alert = True
            alert_reason = f"{stats.consecutive_failures} consecutive failures"

        # Проверка общего количества ошибок
        total_errors = stats.failed_calls
        if total_errors >= self.error_threshold:
            should_alert = True
            alert_reason = f"{total_errors} total errors"

        if not should_alert:
            return False

        # Проверка cooldown
        now = time.time()
        last_alert = self._last_alert_time.get(parser_name, 0)
        if now - last_alert < self.alert_cooldown:
            return False

        # Отправка алерта
        if alert_callback:
            message = (
                f"🚨 Parser Alert: {parser_name}\n\n"
                f"Reason: {alert_reason}\n"
                f"Last error: {stats.last_error}\n"
                f"Success rate: {stats.successful_calls / max(stats.total_calls, 1) * 100:.1f}%"
            )
            await alert_callback(f"Parser Error: {parser_name}", message)
            self._last_alert_time[parser_name] = now
            logger.warning(f"Alert sent for {parser_name}: {alert_reason}")

        return True


# ============================================================================
# Декораторы для удобного использования
# ============================================================================

def resilient(
    retry_config: Optional[RetryConfig] = None,
    fallback_config: Optional[FallbackConfig] = None
) -> Callable:
    """
    Декоратор для добавления retry и fallback к функции.

    Пример:
        @resilient(
            retry_config=RetryConfig(max_retries=3),
            fallback_config=FallbackConfig(default_value=[])
        )
        async def fetch_data():
            ...
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args, **kwargs) -> T:
            # Сначала retry
            try:
                return await retry_with_backoff(func, *args, config=retry_config, **kwargs)
            except MaxRetriesExceeded:
                # Затем fallback
                if fallback_config and fallback_config.default_value is not None:
                    return fallback_config.default_value
                raise

        return wrapper

    return decorator


# ============================================================================
# Экспорт
# ============================================================================

__all__ = [
    # Классы
    "RetryConfig",
    "FallbackConfig",
    "ErrorStats",
    "ErrorSeverity",
    "MaxRetriesExceeded",
    "FallbackError",
    "ResilientParser",
    "AlertManager",

    # Функции
    "retry_with_backoff",
    "with_fallback",
    "calculate_delay",

    # Декораторы
    "resilient",
]
