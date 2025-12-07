import asyncio
import logging
import functools
import random
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class RetryStrategy(str, Enum):
    """Retry strategy types."""
    EXPONENTIAL = "exponential"  # 2^n seconds
    LINEAR = "linear"  # n seconds
    FIBONACCI = "fibonacci"  # Fibonacci sequence
    RANDOM = "random"  # Random backoff


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ParserError(Exception):
    """Базовый класс для ошибок парсеров."""

    pass


class NetworkError(ParserError):
    """Ошибка сети."""

    pass


class ParsingError(ParserError):
    """Ошибка парсинга данных."""

    pass


class RateLimitError(ParserError):
    """Ошибка превышения лимита запросов."""

    pass


class ErrorHandler:
    """Утилита для обработки ошибок и повторных попыток."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def execute_with_retry(
        self, func: Callable, *args, retry_exceptions: Tuple[Type[Exception], ...] = (Exception,), **kwargs
    ) -> Any:
        """
        Выполнение функции с повторными попытками при ошибках.

        Args:
            func: Функция для выполнения
            *args: Позиционные аргументы функции
            retry_exceptions: Кортеж исключений, при которых следует повторить попытку
            **kwargs: Именованные аргументы функции

        Returns:
            Результат выполнения функции

        Raises:
            Исключение, если все попытки неудачны
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except retry_exceptions as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self.base_delay * (2**attempt)  # Экспоненциальная задержка
                    logger.warning(
                        f"Попытка {attempt + 1} выполнения {func.__name__} не удалась: {e}. "
                        f"Повтор через {delay} секунд..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Все {self.max_retries + 1} попытки выполнения {func.__name__} неудачны: {e}")

        raise last_exception


def retry_on_failure(
    max_retries: int = 3, base_delay: float = 1.0, retry_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Декоратор для автоматических повторных попыток выполнения функции.

    Args:
        max_retries: Максимальное количество повторных попыток
        base_delay: Базовая задержка между попытками (в секундах)
        retry_exceptions: Кортеж исключений, при которых следует повторить попытку
    """

    def decorator(func: Callable) -> Callable:
        error_handler = ErrorHandler(max_retries, base_delay)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await error_handler.execute_with_retry(func, *args, retry_exceptions=retry_exceptions, **kwargs)

        return wrapper

    return decorator


class CircuitBreaker:
    """Implements circuit breaker pattern for fault tolerance."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting half-open
            expected_exception: Exception type to track
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED

    def record_success(self):
        """Record successful call."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )

    def can_attempt(self) -> bool:
        """Check if we can attempt a call."""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has elapsed
            if (
                self.last_failure_time
                and datetime.utcnow() - self.last_failure_time
                > timedelta(seconds=self.recovery_timeout)
            ):
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker moved to half-open state")
                return True
            return False

        # HALF_OPEN state - allow one attempt
        return True

    def __call__(self, func):
        """Decorator usage."""
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not self.can_attempt():
                raise Exception(
                    f"Circuit breaker is {self.state}. Service unavailable."
                )

            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except self.expected_exception as e:
                self.record_failure()
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not self.can_attempt():
                raise Exception(
                    f"Circuit breaker is {self.state}. Service unavailable."
                )

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except self.expected_exception as e:
                self.record_failure()
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        exceptions: tuple = (Exception,),
    ):
        """
        Initialize retry config.

        Args:
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries
            strategy: Backoff strategy
            backoff_factor: Factor for exponential backoff
            jitter: Add random jitter to delays
            exceptions: Tuple of exceptions to retry on
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.strategy = strategy
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.exceptions = exceptions

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        if self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.initial_delay * (self.backoff_factor ** attempt)
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.initial_delay * (attempt + 1)
        elif self.strategy == RetryStrategy.FIBONACCI:
            fib_vals = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
            delay = self.initial_delay * fib_vals[min(attempt, len(fib_vals) - 1)]
        elif self.strategy == RetryStrategy.RANDOM:
            delay = random.uniform(self.initial_delay, self.max_delay)
        else:
            delay = self.initial_delay

        # Apply max delay cap
        delay = min(delay, self.max_delay)

        # Add jitter if enabled
        if self.jitter:
            jitter_value = random.uniform(0, delay * 0.1)
            delay += jitter_value

        return delay


def retry_advanced(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    Enhanced decorator for automatic retry with advanced backoff strategies.

    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        strategy: Backoff strategy (exponential, linear, fibonacci, random)
        backoff_factor: Factor for exponential backoff
        jitter: Add random jitter
        exceptions: Exceptions to retry on
        on_retry: Callback function(attempt, delay, exception)

    Example:
        @retry_advanced(max_attempts=3, strategy=RetryStrategy.EXPONENTIAL)
        async def fetch_data():
            return await api.call()
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        strategy=strategy,
        backoff_factor=backoff_factor,
        jitter=jitter,
        exceptions=exceptions,
    )

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    result = await func(*args, **kwargs)
                    return result

                except config.exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Retry {func.__name__}: attempt {attempt + 1}/{config.max_attempts}, "
                            f"delay {delay:.2f}s, error: {str(e)}"
                        )

                        if on_retry:
                            await on_retry(attempt + 1, delay, e) if asyncio.iscoroutinefunction(on_retry) else on_retry(attempt + 1, delay, e)

                        await asyncio.sleep(delay)

            logger.error(
                f"Failed after {config.max_attempts} attempts: {func.__name__}. Error: {str(last_exception)}"
            )
            raise last_exception

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    result = func(*args, **kwargs)
                    return result

                except config.exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Retry {func.__name__}: attempt {attempt + 1}/{config.max_attempts}, "
                            f"delay {delay:.2f}s, error: {str(e)}"
                        )

                        if on_retry:
                            on_retry(attempt + 1, delay, e)

                        asyncio.run(asyncio.sleep(delay))

            logger.error(
                f"Failed after {config.max_attempts} attempts: {func.__name__}. Error: {str(last_exception)}"
            )
            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def handle_errors(
    default_return: Any = None,
    log_error: bool = True,
    exceptions: tuple = (Exception,),
):
    """
    Decorator for graceful error handling with default return value.

    Args:
        default_return: Value to return on error
        log_error: Whether to log the error
        exceptions: Exceptions to catch

    Example:
        @handle_errors(default_return=[], log_error=True)
        async def get_items():
            return await db.query()
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                if log_error:
                    logger.error(
                        f"Error in {func.__name__}: {str(e)}",
                        exc_info=True
                    )
                return default_return

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log_error:
                    logger.error(
                        f"Error in {func.__name__}: {str(e)}",
                        exc_info=True
                    )
                return default_return

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
