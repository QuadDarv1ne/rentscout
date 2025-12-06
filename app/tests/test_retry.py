"""Тесты для retry логики."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from app.utils.retry import retry, RetryError, _calculate_delay


class TestRetryDecorator:
    """Тесты декоратора retry."""

    def test_sync_function_success(self):
        """Тест успешного выполнения синхронной функции."""
        call_count = 0

        @retry(max_attempts=3)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        assert result == "success"
        assert call_count == 1

    def test_sync_function_retry_then_success(self):
        """Тест повторной попытки синхронной функции, заканчивающейся успехом."""
        call_count = 0

        @retry(max_attempts=3)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"

        result = flaky_func()
        assert result == "success"
        assert call_count == 2

    def test_sync_function_all_attempts_fail(self):
        """Тест когда все попытки синхронной функции не удаются."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(RetryError) as exc_info:
            always_fails()

        assert call_count == 3
        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_exception, ValueError)

    @pytest.mark.asyncio
    async def test_async_function_success(self):
        """Тест успешного выполнения асинхронной функции."""
        call_count = 0

        @retry(max_attempts=3)
        async def async_successful():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await async_successful()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_function_retry_then_success(self):
        """Тест повторной попытки асинхронной функции, заканчивающейся успехом."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        async def async_flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"

        result = await async_flaky()
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_function_all_attempts_fail(self):
        """Тест когда все попытки асинхронной функции не удаются."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        async def async_always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")

        with pytest.raises(RetryError) as exc_info:
            await async_always_fails()

        assert call_count == 3
        assert exc_info.value.attempts == 3

    def test_specific_exception_caught(self):
        """Тест перехвата конкретного типа исключения."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01, exceptions=(ValueError,))
        def specific_exception():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Caught error")
            raise RuntimeError("Not caught error")

        with pytest.raises(RuntimeError):
            specific_exception()

        assert call_count == 2  # Поднимает RuntimeError без повторных попыток

    def test_multiple_exceptions(self):
        """Тест перехвата нескольких типов исключений."""
        call_count = 0
        error_type = None

        @retry(
            max_attempts=3,
            initial_delay=0.01,
            exceptions=(ValueError, TypeError),
        )
        def multiple_exceptions():
            nonlocal call_count, error_type
            call_count += 1
            if call_count == 1:
                error_type = "ValueError"
                raise ValueError("Error 1")
            elif call_count == 2:
                error_type = "TypeError"
                raise TypeError("Error 2")
            return "success"

        result = multiple_exceptions()
        assert result == "success"
        assert call_count == 3

    def test_exponential_backoff(self):
        """Тест экспоненциального увеличения задержки."""
        delays = []

        def mock_sleep(delay):
            delays.append(delay)

        call_count = 0

        @retry(
            max_attempts=4,
            initial_delay=1.0,
            exponential_base=2.0,
            jitter=False,
        )
        def delayed_func():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ValueError("Error")
            return "success"

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch("time.sleep", side_effect=mock_sleep):
                result = delayed_func()

        assert result == "success"
        # Задержки: 1.0 * 2^0 = 1.0, 1.0 * 2^1 = 2.0, 1.0 * 2^2 = 4.0
        assert len(delays) == 3
        assert delays[0] <= 1.1  # С jitter
        assert delays[1] <= 2.2
        assert delays[2] <= 4.4

    def test_max_delay_cap(self):
        """Тест ограничения максимальной задержки."""
        delays = []

        def mock_sleep(delay):
            delays.append(delay)

        call_count = 0

        @retry(
            max_attempts=10,
            initial_delay=1.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False,
        )
        def delayed_func():
            nonlocal call_count
            call_count += 1
            if call_count < 10:
                raise ValueError("Error")
            return "success"

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch("time.sleep", side_effect=mock_sleep):
                result = delayed_func()

        assert result == "success"
        # Все задержки должны быть <= 5.0
        for delay in delays:
            assert delay <= 5.1  # С небольшим allowance для jitter

    def test_jitter(self):
        """Тест добавления jitter к задержкам."""
        base_delay = 1.0
        delay = _calculate_delay(0, base_delay, 60.0, 2.0, jitter=True)
        # С jitter задержка будет немного больше базовой
        assert base_delay <= delay <= base_delay * 1.1

    def test_no_jitter(self):
        """Тест без jitter."""
        base_delay = 1.0
        delay = _calculate_delay(0, base_delay, 60.0, 2.0, jitter=False)
        assert delay == base_delay

    def test_retry_error_details(self):
        """Тест содержания информации в RetryError."""
        @retry(max_attempts=2, initial_delay=0.01)
        def failing_func():
            raise ValueError("Original error message")

        with pytest.raises(RetryError) as exc_info:
            failing_func()

        error = exc_info.value
        assert error.attempts == 2
        assert isinstance(error.last_exception, ValueError)
        assert "Original error message" in str(error.last_exception)

    def test_function_arguments_passed(self):
        """Тест передачи аргументов в функцию."""
        @retry(max_attempts=2)
        def func_with_args(a, b, c=None):
            return (a, b, c)

        result = func_with_args(1, 2, c=3)
        assert result == (1, 2, 3)

    @pytest.mark.asyncio
    async def test_async_function_arguments(self):
        """Тест передачи аргументов в асинхронную функцию."""
        @retry(max_attempts=2)
        async def async_func(name, age=None):
            return {"name": name, "age": age}

        result = await async_func("Alice", age=30)
        assert result == {"name": "Alice", "age": 30}

    def test_function_preserves_name_and_doc(self):
        """Тест сохранения имени и документации функции."""
        @retry(max_attempts=3)
        def my_function():
            """My function documentation."""
            return "result"

        assert my_function.__name__ == "my_function"
        assert "My function documentation" in my_function.__doc__


class TestCalculateDelay:
    """Тесты функции расчета задержки."""

    def test_initial_delay(self):
        """Тест первоначальной задержки."""
        delay = _calculate_delay(0, 1.0, 60.0, 2.0, jitter=False)
        assert delay == 1.0

    def test_exponential_growth(self):
        """Тест экспоненциального роста."""
        delay1 = _calculate_delay(1, 1.0, 60.0, 2.0, jitter=False)
        delay2 = _calculate_delay(2, 1.0, 60.0, 2.0, jitter=False)

        assert delay1 == 2.0  # 1.0 * 2^1
        assert delay2 == 4.0  # 1.0 * 2^2

    def test_max_delay_respected(self):
        """Тест соблюдения максимальной задержки."""
        delay = _calculate_delay(10, 1.0, 5.0, 2.0, jitter=False)
        assert delay == 5.0  # Должно быть ограничено до 5.0

    def test_different_bases(self):
        """Тест с разными основаниями экспоненты."""
        delay_base2 = _calculate_delay(2, 1.0, 60.0, 2.0, jitter=False)
        delay_base3 = _calculate_delay(2, 1.0, 60.0, 3.0, jitter=False)

        assert delay_base2 == 4.0   # 1.0 * 2^2
        assert delay_base3 == 9.0   # 1.0 * 3^2
