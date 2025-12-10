"""Performance optimization utilities for parsing and data processing."""

import time
import asyncio
from typing import Callable, Any, Optional, Dict, List
from functools import wraps
from app.utils.logger import logger


def async_timeit(func: Callable) -> Callable:
    """Decorator to measure async function execution time.
    
    Args:
        func: Async function to measure
        
    Returns:
        Wrapped function with timing
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"{func.__name__} took {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper


def timeit(func: Callable) -> Callable:
    """Decorator to measure sync function execution time.
    
    Args:
        func: Function to measure
        
    Returns:
        Wrapped function with timing
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"{func.__name__} took {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper


class BatchProcessor:
    """Process items in batches for better performance."""
    
    def __init__(self, batch_size: int = 100, max_concurrent: int = 5):
        """Initialize batch processor.
        
        Args:
            batch_size: Items per batch
            max_concurrent: Maximum concurrent batches
        """
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process(
        self,
        items: List[Any],
        processor: Callable,
        *args,
        **kwargs
    ) -> List[Any]:
        """Process items in batches.
        
        Args:
            items: Items to process
            processor: Async function to process each batch
            *args: Additional args for processor
            **kwargs: Additional kwargs for processor
            
        Returns:
            List of processed results
        """
        results = []
        batches = self._create_batches(items)
        
        tasks = [
            self._process_batch(batch, processor, *args, **kwargs)
            for batch in batches
        ]
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for batch_result in batch_results:
            if isinstance(batch_result, Exception):
                logger.error(f"Batch processing failed: {batch_result}")
                continue
            results.extend(batch_result)
        
        logger.info(f"Processed {len(items)} items in {len(batches)} batches")
        return results
    
    async def _process_batch(
        self,
        batch: List[Any],
        processor: Callable,
        *args,
        **kwargs
    ) -> List[Any]:
        """Process a single batch with semaphore.
        
        Args:
            batch: Batch of items
            processor: Processing function
            *args: Additional args
            **kwargs: Additional kwargs
            
        Returns:
            Processed batch results
        """
        async with self._semaphore:
            return await processor(batch, *args, **kwargs)
    
    def _create_batches(self, items: List[Any]) -> List[List[Any]]:
        """Split items into batches.
        
        Args:
            items: Items to split
            
        Returns:
            List of batches
        """
        return [
            items[i:i + self.batch_size]
            for i in range(0, len(items), self.batch_size)
        ]


class MemoryOptimizer:
    """Optimize memory usage for large datasets."""
    
    @staticmethod
    def chunk_list(items: List[Any], chunk_size: int = 1000) -> List[List[Any]]:
        """Chunk list into smaller pieces.
        
        Args:
            items: List to chunk
            chunk_size: Size of each chunk
            
        Returns:
            List of chunks
        """
        return [
            items[i:i + chunk_size]
            for i in range(0, len(items), chunk_size)
        ]
    
    @staticmethod
    def deduplicate(items: List[Dict[str, Any]], key: str = "id") -> List[Dict[str, Any]]:
        """Remove duplicates by key with memory efficiency.
        
        Args:
            items: List of dictionaries
            key: Key to use for deduplication
            
        Returns:
            Deduplicated list
        """
        seen = set()
        result = []
        
        for item in items:
            item_key = item.get(key)
            if item_key and item_key not in seen:
                seen.add(item_key)
                result.append(item)
        
        removed = len(items) - len(result)
        if removed > 0:
            logger.info(f"Removed {removed} duplicates")
        
        return result
    
    @staticmethod
    def compress_data(data: str) -> bytes:
        """Compress string data.
        
        Args:
            data: String to compress
            
        Returns:
            Compressed bytes
        """
        import gzip
        return gzip.compress(data.encode())
    
    @staticmethod
    def decompress_data(data: bytes) -> str:
        """Decompress data.
        
        Args:
            data: Compressed bytes
            
        Returns:
            Decompressed string
        """
        import gzip
        return gzip.decompress(data).decode()


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls: int, period: float):
        """Initialize rate limiter.
        
        Args:
            calls: Number of calls allowed
            period: Time period in seconds
        """
        self.calls = calls
        self.period = period
        self._call_times: List[float] = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire permission to make a call (blocks if rate limited)."""
        async with self._lock:
            now = time.time()
            
            # Remove old call times
            self._call_times = [
                t for t in self._call_times
                if now - t < self.period
            ]
            
            # Check if we can make a call
            if len(self._call_times) >= self.calls:
                # Calculate wait time
                oldest = self._call_times[0]
                wait_time = self.period - (now - oldest)
                
                if wait_time > 0:
                    logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    self._call_times = [
                        t for t in self._call_times
                        if now - t < self.period
                    ]
            
            # Record this call
            self._call_times.append(now)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics.
        
        Returns:
            Statistics dictionary
        """
        now = time.time()
        recent_calls = len([
            t for t in self._call_times
            if now - t < self.period
        ])
        
        return {
            "calls_in_period": recent_calls,
            "max_calls": self.calls,
            "period_seconds": self.period,
            "utilization_percent": (recent_calls / self.calls) * 100,
        }


class ParallelExecutor:
    """Execute tasks in parallel with error handling."""
    
    @staticmethod
    async def run_parallel(
        tasks: List[Callable],
        max_concurrent: int = 10,
        return_exceptions: bool = True,
    ) -> List[Any]:
        """Run tasks in parallel with concurrency limit.
        
        Args:
            tasks: List of async callables
            max_concurrent: Max concurrent tasks
            return_exceptions: Whether to return exceptions or raise
            
        Returns:
            List of results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def wrapped_task(task: Callable) -> Any:
            async with semaphore:
                return await task()
        
        wrapped_tasks = [wrapped_task(task) for task in tasks]
        results = await asyncio.gather(*wrapped_tasks, return_exceptions=return_exceptions)
        
        # Log statistics
        successful = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - successful
        
        logger.info(
            f"Parallel execution: {successful} successful, {failed} failed "
            f"out of {len(results)} total"
        )
        
        return results


# Global instances
batch_processor = BatchProcessor()
memory_optimizer = MemoryOptimizer()
parallel_executor = ParallelExecutor()
