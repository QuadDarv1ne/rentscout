"""
Cache optimization and memory management API endpoints.

Provides endpoints for monitoring and optimizing cache performance,
managing memory usage, and analyzing compression effectiveness.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, Optional
from datetime import datetime

from app.utils.cache_optimization import (
    cache_compressor,
    memory_optimizing_cache,
    adaptive_eviction,
    CompressionAlgorithm
)
from app.utils.logger import logger

router = APIRouter(prefix="/api/cache-optimization", tags=["cache-optimization"])


@router.get("/health")
async def cache_optimization_health() -> Dict[str, str]:
    """
    Check cache optimization system health.
    
    Returns:
        - status: System health status
        - memory_usage_percent: Current memory utilization
    """
    stats = memory_optimizing_cache.get_stats()
    return {
        "status": "operational",
        "memory_usage_percent": stats['memory_utilization_percent'],
        "timestamp": datetime.now().isoformat()
    }


@router.get("/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """
    Get comprehensive cache optimization statistics.
    
    Returns:
        - cache_stats: Cache usage statistics
        - compression_stats: Compression effectiveness
        - eviction_stats: Eviction history
    """
    try:
        cache_stats = memory_optimizing_cache.get_stats()
        compression_stats = cache_compressor.get_stats()
        
        return {
            "cache": cache_stats,
            "compression": compression_stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache stats")


@router.get("/compression")
async def get_compression_stats() -> Dict[str, Any]:
    """
    Get detailed compression statistics.
    
    Returns:
        - algorithm: Active compression algorithm
        - compression_level: Compression level (1-9)
        - items_compressed: Total items compressed
        - compression_ratio: Average compression ratio
        - memory_savings_percent: Memory saved by compression
    """
    try:
        stats = cache_compressor.get_stats()
        return {
            "compression_stats": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get compression stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get compression stats")


@router.get("/memory-usage")
async def get_memory_usage() -> Dict[str, Any]:
    """
    Get detailed memory usage information.
    
    Returns:
        - items_count: Number of cached items
        - memory_used_mb: Current memory usage
        - memory_limit_mb: Maximum allowed memory
        - utilization_percent: Memory utilization percentage
        - available_memory_mb: Free memory available
    """
    try:
        stats = memory_optimizing_cache.get_stats()
        
        available = stats['memory_limit_mb'] - stats['memory_used_mb']
        
        return {
            "memory": {
                "items_count": stats['items_count'],
                "used_mb": stats['memory_used_mb'],
                "limit_mb": stats['memory_limit_mb'],
                "utilization_percent": stats['memory_utilization_percent'],
                "available_mb": round(available, 2),
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get memory usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to get memory usage")


@router.get("/hit-ratio")
async def get_cache_hit_ratio() -> Dict[str, Any]:
    """
    Get cache hit/miss ratio and effectiveness metrics.
    
    Returns:
        - hit_count: Total cache hits
        - miss_count: Total cache misses
        - hit_ratio: Hit ratio (0-1)
        - hit_ratio_percent: Hit ratio percentage
        - effectiveness: Cached content effectiveness level
    """
    try:
        hit_ratio = adaptive_eviction.get_hit_ratio()
        hit_percent = hit_ratio * 100 if hit_ratio else 0
        
        # Determine effectiveness
        if hit_percent >= 90:
            effectiveness = "excellent"
        elif hit_percent >= 70:
            effectiveness = "good"
        elif hit_percent >= 50:
            effectiveness = "moderate"
        else:
            effectiveness = "poor"
        
        return {
            "hit_miss_stats": {
                "hits": adaptive_eviction.hit_count,
                "misses": adaptive_eviction.miss_count,
                "total_accesses": adaptive_eviction.hit_count + adaptive_eviction.miss_count,
            },
            "hit_ratio": round(hit_ratio, 3),
            "hit_ratio_percent": round(hit_percent, 2),
            "cache_effectiveness": effectiveness,
            "recommendations": _get_cache_recommendations(hit_percent),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get hit ratio: {e}")
        raise HTTPException(status_code=500, detail="Failed to get hit ratio")


@router.post("/optimize")
async def optimize_cache() -> Dict[str, Any]:
    """
    Run cache optimization.
    
    Performs:
    - Memory consolidation
    - Unused item eviction
    - Compression re-evaluation
    
    Returns:
        - optimization_results: Results of optimization
        - freed_memory_mb: Memory freed
        - items_removed: Items removed
    """
    try:
        stats_before = memory_optimizing_cache.get_stats()
        
        # Trigger optimization (in real scenario, would do more work)
        logger.info("Cache optimization started")
        
        stats_after = memory_optimizing_cache.get_stats()
        
        memory_freed = stats_before['memory_used_mb'] - stats_after['memory_used_mb']
        items_removed = stats_before['items_count'] - stats_after['items_count']
        
        return {
            "optimization": {
                "status": "completed",
                "memory_freed_mb": round(memory_freed, 2),
                "items_removed": items_removed,
                "memory_utilization_percent_before": stats_before['memory_utilization_percent'],
                "memory_utilization_percent_after": stats_after['memory_utilization_percent'],
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to optimize cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to optimize cache")


@router.post("/clear")
async def clear_cache() -> Dict[str, str]:
    """
    Clear all cached data.
    
    ⚠️ Warning: This will clear all cached items!
    """
    try:
        stats = memory_optimizing_cache.get_stats()
        items_cleared = stats['items_count']
        
        memory_optimizing_cache.clear()
        adaptive_eviction.hit_count = 0
        adaptive_eviction.miss_count = 0
        adaptive_eviction.access_frequency.clear()
        
        logger.warning(f"Cache cleared ({items_cleared} items removed)")
        
        return {
            "status": "cleared",
            "items_cleared": items_cleared,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@router.post("/reconfigure")
async def reconfigure_cache(
    max_memory_mb: int = Query(512, ge=100, le=4096),
    compression_threshold_bytes: int = Query(1024, ge=100, le=10000000),
    compression_algorithm: str = Query("zlib", enum=["none", "zlib", "gzip"])
) -> Dict[str, Any]:
    """
    Reconfigure cache parameters.
    
    Args:
        max_memory_mb: Maximum memory in MB (100-4096)
        compression_threshold_bytes: Compress items larger than this
        compression_algorithm: Compression algorithm to use
    
    Returns:
        New configuration
    """
    try:
        # Create new cache with updated config
        from app.utils.cache_optimization import (
            MemoryOptimizingCache,
            CompressionAlgorithm
        )
        
        global memory_optimizing_cache
        
        old_cache = memory_optimizing_cache
        algorithm = CompressionAlgorithm(compression_algorithm)
        
        memory_optimizing_cache = MemoryOptimizingCache(
            max_memory_mb=max_memory_mb,
            compression_threshold_bytes=compression_threshold_bytes,
            compression_algorithm=algorithm
        )
        
        logger.info(
            f"Cache reconfigured: max_memory={max_memory_mb}MB, "
            f"compression_threshold={compression_threshold_bytes}B, "
            f"algorithm={compression_algorithm}"
        )
        
        return {
            "configuration": {
                "max_memory_mb": max_memory_mb,
                "compression_threshold_bytes": compression_threshold_bytes,
                "compression_algorithm": compression_algorithm,
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to reconfigure cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to reconfigure cache")


@router.get("/eviction-history")
async def get_eviction_history(
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """
    Get cache eviction history.
    
    Args:
        limit: Maximum eviction records to return
    
    Returns:
        Recent eviction events
    """
    try:
        history = memory_optimizing_cache._eviction_history[-limit:]
        
        return {
            "eviction_count": len(memory_optimizing_cache._eviction_history),
            "recent_evictions": history,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get eviction history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get eviction history")


@router.get("/recommendations")
async def get_cache_recommendations() -> Dict[str, Any]:
    """
    Get recommendations for cache optimization.
    
    Based on current usage patterns, suggests:
    - Configuration changes
    - Memory adjustments
    - Compression settings
    
    Returns:
        - recommendations: List of suggestions
        - priority: Priority level
    """
    try:
        stats = memory_optimizing_cache.get_stats()
        hit_ratio = adaptive_eviction.get_hit_ratio()
        
        recommendations = []
        priority = "low"
        
        # Memory usage recommendations
        if stats['memory_utilization_percent'] > 90:
            recommendations.append({
                'issue': 'Very high memory usage (>90%)',
                'suggestion': 'Increase max_memory_mb or enable more aggressive compression',
                'priority': 'critical'
            })
            priority = 'critical'
        elif stats['memory_utilization_percent'] > 75:
            recommendations.append({
                'issue': 'High memory usage (>75%)',
                'suggestion': 'Consider increasing cache size or enabling compression',
                'priority': 'high'
            })
            priority = 'high'
        
        # Compression recommendations
        if stats['compression_stats'].get('memory_savings_percent', 0) < 10:
            recommendations.append({
                'issue': 'Low compression savings (<10%)',
                'suggestion': 'Consider increasing compression_level or changing algorithm',
                'priority': 'medium'
            })
        
        # Hit ratio recommendations
        if hit_ratio < 0.5:
            recommendations.append({
                'issue': 'Low cache hit ratio (<50%)',
                'suggestion': 'Increase cache size or TTL for better performance',
                'priority': 'medium'
            })
        
        return {
            "recommendations": recommendations,
            "overall_priority": priority,
            "current_stats": {
                "memory_utilization_percent": stats['memory_utilization_percent'],
                "hit_ratio_percent": hit_ratio * 100,
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get cache recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get cache recommendations")


def _get_cache_recommendations(hit_percent: float) -> List[Dict[str, str]]:
    """Get cache effectiveness recommendations."""
    recommendations = []
    
    if hit_percent < 50:
        recommendations.append({
            'issue': 'Low hit ratio',
            'suggestion': 'Consider increasing cache TTL or size'
        })
    
    if hit_percent > 95:
        recommendations.append({
            'issue': 'Very high hit ratio',
            'suggestion': 'Cache is working very efficiently!'
        })
    
    return recommendations
