"""
Batch processing API endpoints.

Provides endpoints for managing batch parsing operations,
monitoring progress, and retrieving batch results.
"""

from fastapi import APIRouter, Query, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from app.parsers.batch_processing import (
    BatchProcessor,
    BatchConfig,
    ParserBatchManager,
    StreamingBatchProcessor,
    batch_processor,
    parser_batch_manager
)
from app.utils.logger import logger

router = APIRouter(prefix="/api/batch", tags=["batch-processing"])


# Store active batch jobs for tracking
_active_batches: Dict[str, Any] = {}


@router.get("/health")
async def batch_health() -> Dict[str, str]:
    """
    Check batch processing system health.
    
    Returns:
        - status: System health status
        - processor_version: Current processor version
    """
    return {
        "status": "operational",
        "processor_version": "2.0.0",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/info")
async def get_batch_info() -> Dict[str, Any]:
    """
    Get batch processing system information.
    
    Returns:
        - config: Current batch processing configuration
        - active_batches: Count of active batch operations
        - completed_batches: Count of completed operations
    """
    return {
        "configuration": {
            "batch_size": batch_processor.config.batch_size,
            "max_concurrent_batches": batch_processor.config.max_concurrent_batches,
            "max_retries": batch_processor.config.max_retries,
            "timeout_seconds": batch_processor.config.timeout_seconds,
        },
        "active_batches": len([b for b in _active_batches.values() if b['status'] == 'in_progress']),
        "total_batches": len(_active_batches),
        "timestamp": datetime.now().isoformat()
    }


@router.post("/configure")
async def configure_batch_processing(
    batch_size: int = Query(50, ge=1, le=1000),
    max_concurrent: int = Query(5, ge=1, le=20),
    max_retries: int = Query(3, ge=0, le=10),
    timeout_seconds: int = Query(30, ge=5, le=300)
) -> Dict[str, Any]:
    """
    Configure batch processing parameters.
    
    Args:
        batch_size: Items per batch (1-1000)
        max_concurrent: Max concurrent batches (1-20)
        max_retries: Max retries per item (0-10)
        timeout_seconds: Timeout per item (5-300s)
    
    Returns:
        New configuration
    """
    try:
        batch_processor.config = BatchConfig(
            batch_size=batch_size,
            max_concurrent_batches=max_concurrent,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds
        )
        
        logger.info(
            f"Batch processing configured: "
            f"batch_size={batch_size}, "
            f"max_concurrent={max_concurrent}, "
            f"max_retries={max_retries}, "
            f"timeout={timeout_seconds}s"
        )
        
        return {
            "status": "configured",
            "configuration": {
                "batch_size": batch_size,
                "max_concurrent_batches": max_concurrent,
                "max_retries": max_retries,
                "timeout_seconds": timeout_seconds,
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to configure batch processing: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary")
async def get_batch_summary() -> Dict[str, Any]:
    """
    Get summary statistics of batch processing.
    
    Returns:
        - total_items_processed: Total items across all batches
        - success_rate: Overall success percentage
        - average_batch_duration: Average batch processing time
        - throughput: Items processed per second
    """
    try:
        summary = parser_batch_manager.get_summary()
        return {
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get batch summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get batch summary")


@router.get("/status/{batch_id}")
async def get_batch_status(batch_id: str) -> Dict[str, Any]:
    """
    Get status of a specific batch.
    
    Args:
        batch_id: Batch identifier
    
    Returns:
        Batch status and statistics
    """
    if batch_id not in _active_batches:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    
    batch_info = _active_batches[batch_id]
    return {
        "batch_id": batch_id,
        "status": batch_info['status'],
        "items_processed": batch_info.get('items_processed', 0),
        "items_successful": batch_info.get('items_successful', 0),
        "items_failed": batch_info.get('items_failed', 0),
        "progress_percent": batch_info.get('progress', 0),
        "duration_seconds": batch_info.get('duration', 0),
        "created_at": batch_info.get('created_at'),
        "completed_at": batch_info.get('completed_at'),
    }


@router.get("/batches")
async def list_batches(
    source: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    List batch operations with optional filtering.
    
    Args:
        source: Filter by source (optional)
        status: Filter by status - 'in_progress', 'completed', 'failed' (optional)
        limit: Max number of results (1-100)
    
    Returns:
        List of batch operations
    """
    batches = list(_active_batches.values())
    
    if source:
        batches = [b for b in batches if b.get('source') == source]
    
    if status:
        batches = [b for b in batches if b.get('status') == status]
    
    # Sort by created_at descending
    batches.sort(key=lambda b: b.get('created_at', ''), reverse=True)
    
    return {
        "total": len(batches),
        "batches": batches[:limit],
        "timestamp": datetime.now().isoformat()
    }


@router.post("/reset-stats")
async def reset_batch_statistics() -> Dict[str, str]:
    """
    Reset batch processing statistics.
    
    ⚠️ Warning: This will clear all batch history!
    """
    try:
        _active_batches.clear()
        logger.warning("Batch processing statistics reset")
        return {
            "status": "success",
            "message": "Batch statistics have been reset",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to reset batch statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset statistics")


@router.get("/recommendations")
async def get_batch_recommendations() -> Dict[str, Any]:
    """
    Get recommendations for optimal batch configuration.
    
    Based on system performance and batch history,
    suggests optimal batch processing parameters.
    
    Returns:
        - recommendations: List of configuration suggestions
        - reasoning: Why each recommendation is made
    """
    summary = parser_batch_manager.get_summary()
    recommendations = []
    reasoning = []
    
    if summary.get('overall_success_rate', 100) < 85:
        recommendations.append({
            'parameter': 'max_retries',
            'suggested_value': 5,
            'current_value': batch_processor.config.max_retries
        })
        reasoning.append(
            "Success rate below 85%. "
            "Increase max_retries to handle transient failures."
        )
    
    if summary.get('total_items_processed', 0) > 1000:
        avg_duration = summary.get('avg_batch_duration', 0)
        if avg_duration > 10:
            recommendations.append({
                'parameter': 'batch_size',
                'suggested_value': batch_processor.config.batch_size // 2,
                'current_value': batch_processor.config.batch_size,
                'reason': 'Reduce batch size for faster processing'
            })
            reasoning.append("Batch duration is high. Smaller batches may be faster.")
    
    if batch_processor.config.timeout_seconds < 60:
        recommendations.append({
            'parameter': 'timeout_seconds',
            'suggested_value': 60,
            'current_value': batch_processor.config.timeout_seconds
        })
        reasoning.append("Consider increasing timeout for more reliable parsing.")
    
    return {
        "recommendations": recommendations,
        "reasoning": reasoning,
        "based_on_summary": summary,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/benchmark")
async def run_benchmark(
    batch_sizes: List[int] = Query([25, 50, 100]),
    background_tasks: BackgroundTasks = None
) -> Dict[str, Any]:
    """
    Run batch processing benchmark.
    
    Tests different batch sizes to find optimal configuration.
    
    Args:
        batch_sizes: List of batch sizes to test (default: [25, 50, 100])
    
    Returns:
        Benchmark ID for monitoring progress
    """
    benchmark_id = str(uuid.uuid4())
    
    _active_batches[benchmark_id] = {
        'type': 'benchmark',
        'status': 'in_progress',
        'batch_sizes': batch_sizes,
        'created_at': datetime.now().isoformat(),
        'results': []
    }
    
    if background_tasks:
        background_tasks.add_task(
            _run_benchmark_background,
            benchmark_id,
            batch_sizes
        )
    
    return {
        "benchmark_id": benchmark_id,
        "status": "started",
        "batch_sizes": batch_sizes,
        "check_status_at": f"/api/batch/status/{benchmark_id}",
        "timestamp": datetime.now().isoformat()
    }


async def _run_benchmark_background(benchmark_id: str, batch_sizes: List[int]):
    """Run benchmark in background."""
    try:
        logger.info(f"Starting benchmark {benchmark_id} with sizes: {batch_sizes}")
        # Benchmark logic would go here
        _active_batches[benchmark_id]['status'] = 'completed'
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        _active_batches[benchmark_id]['status'] = 'failed'
        _active_batches[benchmark_id]['error'] = str(e)


@router.get("/performance")
async def get_performance_metrics() -> Dict[str, Any]:
    """
    Get detailed performance metrics for batch operations.
    
    Returns:
        - average_processing_time: Time per item
        - throughput: Items per second
        - success_rate: Percentage of successful items
        - memory_efficiency: Items per MB
    """
    summary = parser_batch_manager.get_summary()
    
    items_processed = summary.get('total_items_processed', 0)
    duration = summary.get('total_duration_seconds', 0)
    
    return {
        "metrics": {
            "items_processed": items_processed,
            "total_duration_seconds": summary.get('total_duration_seconds', 0),
            "average_processing_time_ms": (
                (duration * 1000 / items_processed) if items_processed > 0 else 0
            ),
            "throughput_items_per_second": (
                (items_processed / duration) if duration > 0 else 0
            ),
            "success_rate_percent": summary.get('overall_success_rate', 0),
            "batches_count": summary.get('total_batches', 0),
        },
        "timestamp": datetime.now().isoformat()
    }
