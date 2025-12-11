"""
Batch processing utilities for parsers.

Provides optimized batch processing of parsing tasks with:
- Concurrent batch execution
- Memory-efficient streaming
- Error handling and retry logic
- Progress tracking
- Performance monitoring
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable, Coroutine, TypeVar
from dataclasses import dataclass, field
from datetime import datetime
import time
from enum import Enum

from app.models.schemas import PropertyCreate
from app.utils.logger import logger
from app.utils.advanced_metrics import metrics_reporter, MonitorParserExecution
from tenacity import retry, stop_after_attempt, wait_exponential

T = TypeVar('T')


class BatchStatus(str, Enum):
    """Batch processing status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class BatchResult:
    """Result of a batch processing operation."""
    batch_id: str
    source: str
    status: BatchStatus
    items_processed: int = 0
    items_successful: int = 0
    items_failed: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    results: List[PropertyCreate] = field(default_factory=list)
    
    def get_success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.items_processed == 0:
            return 0.0
        return (self.items_successful / self.items_processed) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'batch_id': self.batch_id,
            'source': self.source,
            'status': self.status.value,
            'items_processed': self.items_processed,
            'items_successful': self.items_successful,
            'items_failed': self.items_failed,
            'success_rate_percent': round(self.get_success_rate(), 2),
            'duration_seconds': round(self.duration_seconds, 2),
            'error_count': len(self.errors),
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
        }


@dataclass
class BatchConfig:
    """Configuration for batch processing."""
    batch_size: int = 50  # Items per batch
    max_concurrent_batches: int = 5
    max_retries: int = 3
    timeout_seconds: int = 30
    collect_errors: bool = True
    progress_callback: Optional[Callable[[int, int], None]] = None
    
    def validate(self):
        """Validate configuration."""
        assert self.batch_size > 0, "batch_size must be > 0"
        assert self.max_concurrent_batches > 0, "max_concurrent_batches must be > 0"
        assert self.max_retries >= 0, "max_retries must be >= 0"
        assert self.timeout_seconds > 0, "timeout_seconds must be > 0"


class BatchProcessor:
    """Process items in batches with concurrent execution."""
    
    def __init__(self, config: Optional[BatchConfig] = None):
        """
        Initialize batch processor.
        
        Args:
            config: Batch processing configuration
        """
        self.config = config or BatchConfig()
        self.config.validate()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_batches)
        self._batch_counter = 0
    
    async def process_batch(
        self,
        items: List[T],
        processor_func: Callable[[T], Coroutine[Any, Any, PropertyCreate]],
        source: str,
        batch_id: Optional[str] = None
    ) -> BatchResult:
        """
        Process a list of items in batches.
        
        Args:
            items: Items to process
            processor_func: Async function to process each item
            source: Source name for logging
            batch_id: Optional batch identifier
        
        Returns:
            BatchResult with processing results
        """
        if batch_id is None:
            self._batch_counter += 1
            batch_id = f"{source}_{self._batch_counter}"
        
        result = BatchResult(
            batch_id=batch_id,
            source=source,
            status=BatchStatus.IN_PROGRESS
        )
        
        start_time = time.perf_counter()
        
        try:
            # Split into batches
            batches = [
                items[i:i + self.config.batch_size]
                for i in range(0, len(items), self.config.batch_size)
            ]
            
            logger.info(f"Processing {len(items)} items in {len(batches)} batches")
            
            # Process batches concurrently
            tasks = [
                self._process_single_batch(
                    batch, 
                    processor_func, 
                    batch_idx, 
                    len(batches),
                    result
                )
                for batch_idx, batch in enumerate(batches)
            ]
            
            await asyncio.gather(*tasks, return_exceptions=False)
            
            result.status = BatchStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            result.status = BatchStatus.FAILED
            if self.config.collect_errors:
                result.errors.append({
                    'error': str(e),
                    'type': type(e).__name__,
                    'timestamp': datetime.now().isoformat()
                })
        
        finally:
            result.end_time = datetime.now()
            result.duration_seconds = time.perf_counter() - start_time
        
        # Report metrics
        metrics_reporter.record_parser_success(
            source=source,
            items=result.items_successful,
            duration=result.duration_seconds
        )
        
        logger.info(
            f"Batch {batch_id} completed: "
            f"{result.items_successful}/{result.items_processed} "
            f"({result.get_success_rate():.1f}%) "
            f"in {result.duration_seconds:.2f}s"
        )
        
        return result
    
    async def _process_single_batch(
        self,
        batch: List[T],
        processor_func: Callable[[T], Coroutine[Any, Any, PropertyCreate]],
        batch_idx: int,
        total_batches: int,
        result: BatchResult
    ):
        """Process a single batch of items."""
        async with self._semaphore:
            for item in batch:
                try:
                    result.items_processed += 1
                    
                    # Apply retry logic
                    processed_item = await self._process_with_retry(
                        processor_func(item)
                    )
                    
                    result.results.append(processed_item)
                    result.items_successful += 1
                    
                except Exception as e:
                    result.items_failed += 1
                    if self.config.collect_errors:
                        result.errors.append({
                            'item': str(item)[:100],
                            'error': str(e),
                            'type': type(e).__name__,
                            'timestamp': datetime.now().isoformat()
                        })
                    logger.warning(f"Failed to process item: {e}")
            
            # Progress callback
            if self.config.progress_callback:
                self.config.progress_callback(batch_idx + 1, total_batches)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _process_with_retry(
        self,
        coro: Coroutine[Any, Any, PropertyCreate]
    ) -> PropertyCreate:
        """
        Process item with automatic retry.
        
        Args:
            coro: Coroutine to execute
        
        Returns:
            Processed item
        """
        return await asyncio.wait_for(coro, timeout=self.config.timeout_seconds)


class ParserBatchManager:
    """Manage batch parsing from multiple sources."""
    
    def __init__(self, config: Optional[BatchConfig] = None):
        """
        Initialize parser batch manager.
        
        Args:
            config: Batch processing configuration
        """
        self.config = config or BatchConfig()
        self.processor = BatchProcessor(self.config)
        self._source_batches: Dict[str, List[BatchResult]] = {}
    
    async def parse_multiple_sources(
        self,
        sources_data: Dict[str, List[T]],
        parser_funcs: Dict[str, Callable[[T], Coroutine[Any, Any, PropertyCreate]]]
    ) -> Dict[str, BatchResult]:
        """
        Parse from multiple sources concurrently.
        
        Args:
            sources_data: Dict mapping source names to item lists
            parser_funcs: Dict mapping source names to parser functions
        
        Returns:
            Dict mapping source names to BatchResults
        """
        tasks = {
            source: self.processor.process_batch(
                items=sources_data[source],
                processor_func=parser_funcs[source],
                source=source
            )
            for source in sources_data.keys()
            if source in parser_funcs
        }
        
        results = await asyncio.gather(*tasks.values(), return_exceptions=False)
        
        return {
            source: result
            for source, result in zip(tasks.keys(), results)
        }
    
    def get_batch_history(self, source: str) -> List[BatchResult]:
        """Get batch processing history for a source."""
        return self._source_batches.get(source, [])
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all batch operations."""
        all_results = [
            result
            for results in self._source_batches.values()
            for result in results
        ]
        
        if not all_results:
            return {"message": "No batch operations"}
        
        total_processed = sum(r.items_processed for r in all_results)
        total_successful = sum(r.items_successful for r in all_results)
        total_failed = sum(r.items_failed for r in all_results)
        total_duration = sum(r.duration_seconds for r in all_results)
        
        return {
            'total_batches': len(all_results),
            'total_items_processed': total_processed,
            'total_items_successful': total_successful,
            'total_items_failed': total_failed,
            'overall_success_rate': (total_successful / total_processed * 100) if total_processed > 0 else 0,
            'total_duration_seconds': round(total_duration, 2),
            'avg_batch_duration': round(total_duration / len(all_results), 2) if all_results else 0,
        }


@dataclass
class StreamBatchConfig:
    """Configuration for streaming batch processing."""
    chunk_size: int = 100
    memory_limit_mb: int = 512
    flush_interval_seconds: int = 30


class StreamingBatchProcessor:
    """
    Process large datasets using streaming with memory limits.
    
    Useful for processing large numbers of items without
    loading everything into memory at once.
    """
    
    def __init__(self, config: Optional[StreamBatchConfig] = None):
        """Initialize streaming processor."""
        self.config = config or StreamBatchConfig()
        self._processed_count = 0
        self._current_batch: List[PropertyCreate] = []
        self._last_flush_time = time.perf_counter()
    
    async def process_stream(
        self,
        data_generator: Callable[[], Coroutine[Any, Any, Any]],
        processor_func: Callable[[Any], Coroutine[Any, Any, PropertyCreate]],
        sink_func: Callable[[List[PropertyCreate]], Coroutine[Any, Any, None]],
        source: str
    ) -> Dict[str, Any]:
        """
        Process data from generator with streaming and batching.
        
        Args:
            data_generator: Async generator providing items
            processor_func: Function to process each item
            sink_func: Function to handle completed batches
            source: Source name for logging
        
        Returns:
            Processing statistics
        """
        start_time = time.perf_counter()
        stats = {
            'source': source,
            'items_processed': 0,
            'items_successful': 0,
            'items_failed': 0,
            'batches_processed': 0,
            'duration_seconds': 0,
            'throughput_items_per_sec': 0,
        }
        
        try:
            async for item in data_generator():
                try:
                    processed = await processor_func(item)
                    self._current_batch.append(processed)
                    stats['items_successful'] += 1
                    stats['items_processed'] += 1
                    
                    # Flush if needed
                    should_flush = (
                        len(self._current_batch) >= self.config.chunk_size or
                        time.perf_counter() - self._last_flush_time >= self.config.flush_interval_seconds
                    )
                    
                    if should_flush and self._current_batch:
                        await sink_func(self._current_batch)
                        stats['batches_processed'] += 1
                        logger.info(
                            f"Flushed batch of {len(self._current_batch)} items"
                        )
                        self._current_batch = []
                        self._last_flush_time = time.perf_counter()
                
                except Exception as e:
                    stats['items_failed'] += 1
                    stats['items_processed'] += 1
                    logger.warning(f"Failed to process item: {e}")
            
            # Final flush
            if self._current_batch:
                await sink_func(self._current_batch)
                stats['batches_processed'] += 1
                logger.info(f"Flushed final batch of {len(self._current_batch)} items")
            
            duration = time.perf_counter() - start_time
            stats['duration_seconds'] = round(duration, 2)
            stats['throughput_items_per_sec'] = round(
                stats['items_processed'] / duration if duration > 0 else 0, 2
            )
            
        except Exception as e:
            logger.error(f"Stream processing failed: {e}")
            raise
        
        return stats


# Global instances
batch_processor = BatchProcessor()
parser_batch_manager = ParserBatchManager()
streaming_processor = StreamingBatchProcessor()
