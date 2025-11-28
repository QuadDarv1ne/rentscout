import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.utils.error_handler import ErrorHandler, NetworkError, ParserError, ParsingError, retry_on_failure


@pytest.mark.asyncio
async def test_error_handler_execute_with_retry_success():
    """Тест успешного выполнения функции без ошибок."""
    handler = ErrorHandler(max_retries=3, base_delay=0.1)

    async def success_func():
        return "success"

    result = await handler.execute_with_retry(success_func)
    assert result == "success"


@pytest.mark.asyncio
async def test_error_handler_execute_with_retry_eventual_success():
    """Тест успешного выполнения функции после нескольких попыток."""
    handler = ErrorHandler(max_retries=3, base_delay=0.1)

    attempt_count = 0

    async def fail_then_succeed_func():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise Exception("Temporary failure")
        return "success"

    result = await handler.execute_with_retry(fail_then_succeed_func)
    assert result == "success"
    assert attempt_count == 3


@pytest.mark.asyncio
async def test_error_handler_execute_with_retry_all_failures():
    """Тест случая, когда все попытки завершаются неудачей."""
    handler = ErrorHandler(max_retries=2, base_delay=0.1)

    async def always_fail_func():
        raise Exception("Permanent failure")

    with pytest.raises(Exception, match="Permanent failure"):
        await handler.execute_with_retry(always_fail_func)


@pytest.mark.asyncio
async def test_error_handler_execute_with_specific_exceptions():
    """Тест повторных попыток только для определенных исключений."""
    handler = ErrorHandler(max_retries=2, base_delay=0.1)

    attempt_count = 0

    async def selective_fail_func():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            raise ValueError("Should retry")  # Это исключение должно вызвать повтор
        elif attempt_count == 2:
            raise RuntimeError("Should not retry")  # Это исключение не должно вызывать повтор
        return "success"

    # Попробуем с ValueError в списке retry_exceptions
    # Вторая попытка вызовет RuntimeError, которое не в списке retry_exceptions,
    # поэтому должно быть выброшено как есть
    with pytest.raises(RuntimeError, match="Should not retry"):
        await handler.execute_with_retry(selective_fail_func, retry_exceptions=(ValueError,))

    assert attempt_count == 2  # Должно быть две попытки


@pytest.mark.asyncio
async def test_retry_on_failure_decorator():
    """Тест декоратора retry_on_failure."""
    attempt_count = 0

    @retry_on_failure(max_retries=2, base_delay=0.1)
    async def decorated_func():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise Exception("Temporary failure")
        return "success"

    result = await decorated_func()
    assert result == "success"
    assert attempt_count == 2


@pytest.mark.asyncio
async def test_custom_exceptions():
    """Тест пользовательских исключений."""
    # Проверяем, что пользовательские исключения могут быть созданы
    parser_error = ParserError("Parser error")
    network_error = NetworkError("Network error")
    parsing_error = ParsingError("Parsing error")

    assert isinstance(parser_error, Exception)
    assert isinstance(network_error, ParserError)
    assert isinstance(parsing_error, ParserError)

    # Проверяем, что они имеют правильные сообщения
    assert str(parser_error) == "Parser error"
    assert str(network_error) == "Network error"
    assert str(parsing_error) == "Parsing error"
