import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


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
