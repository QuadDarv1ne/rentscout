"""Tests for optimization utilities."""

import pytest
import asyncio
from app.utils.optimization import (
    BatchProcessor,
    MemoryOptimizer,
    RateLimiter,
    ParallelExecutor,
    async_timeit,
    timeit,
)


@pytest.mark.asyncio
async def test_batch_processor():
    """Test batch processing."""
    processor = BatchProcessor(batch_size=3, max_concurrent=2)
    
    # Create test items
    items = list(range(10))
    
    # Test processor function
    async def process_batch(batch):
        await asyncio.sleep(0.01)
        return [x * 2 for x in batch]
    
    # Process items
    results = await processor.process(items, process_batch)
    
    assert len(results) == 10
    assert results == [x * 2 for x in items]


def test_memory_optimizer_deduplicate():
    """Test deduplication."""
    items = [
        {"id": 1, "name": "item1"},
        {"id": 2, "name": "item2"},
        {"id": 1, "name": "item1_duplicate"},
        {"id": 3, "name": "item3"},
    ]
    
    result = MemoryOptimizer.deduplicate(items, key="id")
    
    assert len(result) == 3
    assert all(item["id"] in [1, 2, 3] for item in result)


def test_memory_optimizer_chunk():
    """Test list chunking."""
    items = list(range(100))
    chunks = MemoryOptimizer.chunk_list(items, chunk_size=10)
    
    assert len(chunks) == 10
    assert all(len(chunk) == 10 for chunk in chunks)
    
    # Verify all items are present
    flat_items = [item for chunk in chunks for item in chunk]
    assert flat_items == items


def test_memory_optimizer_compression():
    """Test data compression."""
    data = "Hello, World!" * 100
    
    # Compress
    compressed = MemoryOptimizer.compress_data(data)
    assert len(compressed) < len(data.encode())
    
    # Decompress
    decompressed = MemoryOptimizer.decompress_data(compressed)
    assert decompressed == data


@pytest.mark.asyncio
async def test_rate_limiter():
    """Test rate limiting."""
    limiter = RateLimiter(calls=3, period=1.0)
    
    # Should allow first 3 calls immediately
    start = asyncio.get_event_loop().time()
    for _ in range(3):
        await limiter.acquire()
    
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 0.1  # Should be nearly instant
    
    # 4th call should wait
    start = asyncio.get_event_loop().time()
    await limiter.acquire()
    elapsed = asyncio.get_event_loop().time() - start
    
    # Should have waited ~1 second
    assert elapsed >= 0.9


def test_rate_limiter_stats():
    """Test rate limiter statistics."""
    limiter = RateLimiter(calls=5, period=10.0)
    stats = limiter.get_stats()
    
    assert "calls_in_period" in stats
    assert "max_calls" in stats
    assert stats["max_calls"] == 5
    assert stats["period_seconds"] == 10.0


@pytest.mark.asyncio
async def test_parallel_executor():
    """Test parallel task execution."""
    # Create test tasks
    async def task(value):
        await asyncio.sleep(0.01)
        return value * 2
    
    tasks = [lambda v=i: task(v) for i in range(10)]
    
    # Execute in parallel
    results = await ParallelExecutor.run_parallel(tasks, max_concurrent=5)
    
    assert len(results) == 10
    assert all(isinstance(r, int) for r in results)


@pytest.mark.asyncio
async def test_parallel_executor_with_errors():
    """Test parallel execution with some failing tasks."""
    async def good_task():
        await asyncio.sleep(0.01)
        return "success"
    
    async def bad_task():
        await asyncio.sleep(0.01)
        raise ValueError("Task failed")
    
    tasks = [good_task, bad_task, good_task, bad_task]
    
    # Execute with return_exceptions=True
    results = await ParallelExecutor.run_parallel(
        tasks,
        max_concurrent=2,
        return_exceptions=True,
    )
    
    assert len(results) == 4
    successes = [r for r in results if r == "success"]
    errors = [r for r in results if isinstance(r, Exception)]
    
    assert len(successes) == 2
    assert len(errors) == 2


@pytest.mark.asyncio
async def test_async_timeit_decorator():
    """Test async timing decorator."""
    @async_timeit
    async def slow_function():
        await asyncio.sleep(0.1)
        return "done"
    
    result = await slow_function()
    assert result == "done"


def test_timeit_decorator():
    """Test sync timing decorator."""
    @timeit
    def slow_function():
        import time
        time.sleep(0.05)
        return "done"
    
    result = slow_function()
    assert result == "done"


@pytest.mark.asyncio
async def test_batch_processor_with_errors():
    """Test batch processing with some failing batches."""
    processor = BatchProcessor(batch_size=2, max_concurrent=2)
    
    items = list(range(6))
    
    async def process_batch(batch):
        if batch[0] == 2:  # Fail for batch starting with 2
            raise ValueError("Batch failed")
        return [x * 2 for x in batch]
    
    results = await processor.process(items, process_batch)
    
    # Should have results from successful batches only
    assert len(results) < len(items) * 2


def test_memory_optimizer_empty_list():
    """Test deduplication with empty list."""
    result = MemoryOptimizer.deduplicate([])
    assert result == []


def test_memory_optimizer_no_duplicates():
    """Test deduplication with no duplicates."""
    items = [
        {"id": 1, "name": "item1"},
        {"id": 2, "name": "item2"},
        {"id": 3, "name": "item3"},
    ]
    
    result = MemoryOptimizer.deduplicate(items)
    assert len(result) == len(items)


@pytest.mark.asyncio
async def test_rate_limiter_concurrent():
    """Test rate limiter with concurrent requests."""
    limiter = RateLimiter(calls=5, period=1.0)
    
    async def make_call():
        await limiter.acquire()
        return True
    
    # Make 10 concurrent calls
    tasks = [make_call() for _ in range(10)]
    results = await asyncio.gather(*tasks)
    
    assert all(results)
    assert len(results) == 10
