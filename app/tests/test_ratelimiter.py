import asyncio
import pytest
import time

from app.utils.ratelimiter import RateLimiter


def test_rate_limiter_basic():
    """Test basic rate limiting functionality."""
    # Create a rate limiter that allows 3 requests per second
    limiter = RateLimiter(max_requests=3, time_window=1)

    # These should not block
    start_time = time.time()
    asyncio.run(limiter.acquire("test"))
    asyncio.run(limiter.acquire("test"))
    asyncio.run(limiter.acquire("test"))
    end_time = time.time()

    # Should be almost instant (well under 0.1 seconds)
    assert end_time - start_time < 0.1


def test_rate_limiter_blocking():
    """Test that rate limiter blocks when limit is exceeded."""
    # Create a rate limiter that allows 2 requests per second
    limiter = RateLimiter(max_requests=2, time_window=1)

    # These should not block
    start_time = time.time()
    asyncio.run(limiter.acquire("test"))
    asyncio.run(limiter.acquire("test"))

    # This should block for about 1 second
    asyncio.run(limiter.acquire("test"))
    end_time = time.time()

    # Should have taken at least 1 second (minus a small margin for timing inaccuracies)
    assert end_time - start_time >= 0.9


def test_rate_limiter_different_keys():
    """Test that rate limiter works independently for different keys."""
    # Create a rate limiter that allows 1 request per second
    limiter = RateLimiter(max_requests=1, time_window=1)

    # These should not block because they use different keys
    start_time = time.time()
    asyncio.run(limiter.acquire("key1"))
    asyncio.run(limiter.acquire("key2"))
    asyncio.run(limiter.acquire("key3"))
    end_time = time.time()

    # Should be almost instant (well under 0.1 seconds)
    assert end_time - start_time < 0.1


def test_rate_limiter_cleanup():
    """Test that old requests are cleaned up properly."""
    # Create a rate limiter that allows 1 request per second
    limiter = RateLimiter(max_requests=1, time_window=1)

    # Make a request
    asyncio.run(limiter.acquire("test"))

    # Wait for the time window to pass
    time.sleep(1.1)

    # This should not block because the previous request is now outside the time window
    start_time = time.time()
    asyncio.run(limiter.acquire("test"))
    end_time = time.time()

    # Should be almost instant (well under 0.1 seconds)
    assert end_time - start_time < 0.1


def test_rate_limiter_reset():
    """Test that rate limiter can be reset."""
    # Create a rate limiter that allows 1 request per second
    limiter = RateLimiter(max_requests=1, time_window=1)

    # Make a request
    asyncio.run(limiter.acquire("test"))

    # This should block
    start_time = time.time()
    asyncio.run(limiter.acquire("test"))
    end_time = time.time()

    # Should have taken at least 1 second
    assert end_time - start_time >= 0.9

    # Reset the limiter
    limiter.reset("test")

    # This should not block after reset
    start_time = time.time()
    asyncio.run(limiter.acquire("test"))
    end_time = time.time()

    # Should be almost instant (well under 0.1 seconds)
    assert end_time - start_time < 0.1
