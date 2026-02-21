"""Утилиты для повторных попыток запросов (retry logic)."""

import asyncio
import functools
import random
from typing import Callable, Optional, Type, Tuple, TypeVar, Any

from app.utils.logger import logger

T = TypeVar("T")


class RetryError(Exception):
    """Исключение, выбрасываемое когда истощены все повторные попытки."""

    def __init__(self, attempts: int, last_exception: Exception):
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(
            f"Failed after {attempts} attempts. Last error: {str(last_exception)}"
        )


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Декоратор для повторных попыток вызова функции при ошибке.

    Args:
        max_attempts: Максимальное количество попыток (включая первую)
        initial_delay: Начальная задержка между попытками в секундах
        max_delay: Максимальная задержка между попытками в секундах
        exponential_base: База для экспоненциального увеличения задержки
        jitter: Добавлять ли случайную составляющую к задержке
        exceptions: Кортеж типов исключений, при которых нужно повторять попытку

    Returns:
        Декоратор функции

    Example:
        @retry(max_attempts=3, initial_delay=1.0)
        async def fetch_data():
            return await http_client.get("/api/data")
    """

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> Any:
                return await _retry_async(
                    func,
                    args,
                    kwargs,
                    max_attempts,
                    initial_delay,
                    max_delay,
                    exponential_base,
                    jitter,
                    exceptions,
                )

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> Any:
                return _retry_sync(
                    func,
                    args,
                    kwargs,
                    max_attempts,
                    initial_delay,
                    max_delay,
                    exponential_base,
                    jitter,
                    exceptions,
                )

            return sync_wrapper

    return decorator


async def _retry_async(
    func: Callable,
    args: Tuple,
    kwargs: dict,
    max_attempts: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
    exceptions: Tuple[Type[Exception], ...],
) -> Any:
    """Вспомогательная функция для повторных попыток асинхронной функции."""
    last_exception: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(f"Attempt {attempt}/{max_attempts} for {func.__name__}")
            return await func(*args, **kwargs)

        except exceptions as e:
            last_exception = e
            
            if attempt < max_attempts:
                delay = _calculate_delay(
                    attempt - 1, initial_delay, max_delay, exponential_base, jitter
                )
                logger.warning(
                    f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"All {max_attempts} attempts failed for {func.__name__}. "
                    f"Last error: {e}"
                )

    raise RetryError(max_attempts, last_exception) if last_exception else RuntimeError(
        f"Failed to execute {func.__name__} after {max_attempts} attempts"
    )


def _retry_sync(
    func: Callable,
    args: Tuple,
    kwargs: dict,
    max_attempts: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
    exceptions: Tuple[Type[Exception], ...],
) -> Any:
    """Вспомогательная функция для повторных попыток синхронной функции."""
    import time
    last_exception: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(f"Attempt {attempt}/{max_attempts} for {func.__name__}")
            return func(*args, **kwargs)

        except exceptions as e:
            last_exception = e
            
            if attempt < max_attempts:
                delay = _calculate_delay(
                    attempt - 1, initial_delay, max_delay, exponential_base, jitter
                )
                logger.warning(
                    f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"All {max_attempts} attempts failed for {func.__name__}. "
                    f"Last error: {e}"
                )

    raise RetryError(max_attempts, last_exception) if last_exception else RuntimeError(
        f"Failed to execute {func.__name__} after {max_attempts} attempts"
    )


def _calculate_delay(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
) -> float:
    """
    Вычисляет задержку между попытками.

    Использует экспоненциальное увеличение с опциональной рандомной составляющей.
    """
    # Экспоненциальное увеличение: initial_delay * (exponential_base ** attempt)
    delay = initial_delay * (exponential_base ** attempt)
    # Ограничиваем максимальной задержкой
    delay = min(delay, max_delay)

    # Добавляем jitter (случайную составляющую)
    if jitter:
        jitter_amount = delay * random.uniform(0, 0.1)
        delay += jitter_amount

    return delay
