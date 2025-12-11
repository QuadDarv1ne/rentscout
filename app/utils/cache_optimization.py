"""
Cache memory optimization utilities.

Provides memory-efficient caching with:
- Compression support
- Memory pooling
- Adaptive eviction policies
- Memory usage monitoring
- Compression ratio analysis
"""

import zlib
import json
import pickle
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import sys

from app.utils.logger import logger
from app.utils.advanced_metrics import metrics_reporter


class CompressionAlgorithm(str, Enum):
    """Supported compression algorithms."""
    NONE = "none"
    ZLIB = "zlib"
    GZIP = "gzip"


@dataclass
class CacheMemoryStats:
    """Cache memory statistics."""
    uncompressed_size: int = 0
    compressed_size: int = 0
    items_count: int = 0
    compression_ratio: float = 0.0
    memory_savings_percent: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
        if self.uncompressed_size > 0 and self.compressed_size > 0:
            self.compression_ratio = self.uncompressed_size / self.compressed_size
            self.memory_savings_percent = (
                (self.uncompressed_size - self.compressed_size) /
                self.uncompressed_size * 100
            )


class CacheCompressor:
    """Compress cache values to reduce memory usage."""
    
    def __init__(
        self,
        algorithm: CompressionAlgorithm = CompressionAlgorithm.ZLIB,
        compression_level: int = 6
    ):
        """
        Initialize cache compressor.
        
        Args:
            algorithm: Compression algorithm to use
            compression_level: Compression level (1-9 for zlib)
        """
        self.algorithm = algorithm
        self.compression_level = max(1, min(9, compression_level))
        self.stats = CacheMemoryStats()
    
    def compress(self, value: Any) -> bytes:
        """
        Compress a value.
        
        Args:
            value: Value to compress
        
        Returns:
            Compressed bytes
        """
        if self.algorithm == CompressionAlgorithm.NONE:
            return pickle.dumps(value)
        
        # Serialize first
        serialized = pickle.dumps(value)
        self.stats.uncompressed_size += sys.getsizeof(serialized)
        
        # Compress
        if self.algorithm == CompressionAlgorithm.ZLIB:
            compressed = zlib.compress(serialized, self.compression_level)
        else:  # GZIP
            compressed = zlib.compress(serialized, self.compression_level | 0x20)
        
        self.stats.compressed_size += sys.getsizeof(compressed)
        self.stats.items_count += 1
        
        return compressed
    
    def decompress(self, data: bytes) -> Any:
        """
        Decompress a value.
        
        Args:
            data: Compressed bytes
        
        Returns:
            Decompressed value
        """
        if self.algorithm == CompressionAlgorithm.NONE:
            return pickle.loads(data)
        
        # Decompress
        try:
            decompressed = zlib.decompress(data)
        except Exception:
            # Try with different decompression method
            decompressed = zlib.decompress(data, wbits=16 + zlib.MAX_WBITS)
        
        # Deserialize
        return pickle.loads(decompressed)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get compression statistics."""
        return {
            'algorithm': self.algorithm.value,
            'compression_level': self.compression_level,
            'items_compressed': self.stats.items_count,
            'uncompressed_size_bytes': self.stats.uncompressed_size,
            'compressed_size_bytes': self.stats.compressed_size,
            'compression_ratio': round(self.stats.compression_ratio, 2),
            'memory_savings_percent': round(self.stats.memory_savings_percent, 2),
        }
    
    def reset_stats(self):
        """Reset compression statistics."""
        self.stats = CacheMemoryStats()


class MemoryOptimizingCache:
    """
    Cache implementation with memory optimization.
    
    Automatically compresses values to reduce memory usage
    while maintaining performance.
    """
    
    def __init__(
        self,
        max_memory_mb: int = 512,
        compression_threshold_bytes: int = 1024,
        compression_algorithm: CompressionAlgorithm = CompressionAlgorithm.ZLIB
    ):
        """
        Initialize memory-optimizing cache.
        
        Args:
            max_memory_mb: Maximum memory usage in MB
            compression_threshold_bytes: Compress values larger than this
            compression_algorithm: Algorithm to use for compression
        """
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.compression_threshold = compression_threshold_bytes
        self.compressor = CacheCompressor(compression_algorithm)
        self._cache: Dict[str, tuple] = {}  # (value, size, timestamp)
        self._current_memory = 0
        self._eviction_history: List[Dict[str, Any]] = []
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """
        Set cache value with automatic compression.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds
        """
        # Determine if compression needed
        value_size = sys.getsizeof(value)
        should_compress = value_size > self.compression_threshold
        
        if should_compress:
            compressed_value = self.compressor.compress(value)
            actual_value = compressed_value
            actual_size = sys.getsizeof(compressed_value)
            is_compressed = True
        else:
            actual_value = value
            actual_size = value_size
            is_compressed = False
        
        # Remove old value if exists
        if key in self._cache:
            old_value, old_size, _ = self._cache[key]
            self._current_memory -= old_size
        
        # Check memory limit and evict if needed
        new_total = self._current_memory + actual_size
        if new_total > self.max_memory_bytes:
            self._evict_until_fit(actual_size)
        
        # Store value
        expiry = None
        if ttl_seconds:
            expiry = datetime.now() + timedelta(seconds=ttl_seconds)
        
        self._cache[key] = (actual_value, actual_size, expiry, is_compressed)
        self._current_memory += actual_size
        
        logger.debug(
            f"Cached {key}: {value_size}B → {actual_size}B "
            f"(compressed={is_compressed})"
        )
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
        
        Returns:
            Cached value or None
        """
        if key not in self._cache:
            return None
        
        value, size, expiry, is_compressed = self._cache[key]
        
        # Check expiry
        if expiry and expiry < datetime.now():
            del self._cache[key]
            self._current_memory -= size
            return None
        
        # Decompress if needed
        if is_compressed:
            return self.compressor.decompress(value)
        return value
    
    def _evict_until_fit(self, needed_space: int):
        """
        Evict items until there's enough space.
        
        Args:
            needed_space: Space needed in bytes
        """
        freed = 0
        evicted_items = []
        
        # Sort by last access time (oldest first)
        sorted_items = sorted(
            self._cache.items(),
            key=lambda x: x[1][2] or datetime.min
        )
        
        for key, (value, size, expiry, is_compressed) in sorted_items:
            if freed >= needed_space:
                break
            
            del self._cache[key]
            freed += size
            self._current_memory -= size
            evicted_items.append({
                'key': key,
                'size': size,
                'reason': 'memory_limit',
                'timestamp': datetime.now().isoformat()
            })
            
            metrics_reporter.record_cache_eviction('optimized', 'memory')
        
        self._eviction_history.extend(evicted_items)
        logger.info(f"Evicted {len(evicted_items)} items to free {freed}B")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'items_count': len(self._cache),
            'memory_used_mb': round(self._current_memory / (1024 * 1024), 2),
            'memory_limit_mb': round(self.max_memory_bytes / (1024 * 1024), 2),
            'memory_utilization_percent': round(
                (self._current_memory / self.max_memory_bytes) * 100, 2
            ),
            'compression_stats': self.compressor.get_stats(),
            'evictions_total': len(self._eviction_history),
        }
    
    def clear(self):
        """Clear all cache."""
        self._cache.clear()
        self._current_memory = 0
        logger.info("Cache cleared")


class AdaptiveEvictionPolicy:
    """
    Adaptive cache eviction policy based on access patterns.
    
    Automatically adjusts eviction strategy based on:
    - Cache hit/miss ratio
    - Item access frequency
    - Memory pressure
    """
    
    def __init__(self):
        """Initialize adaptive eviction policy."""
        self.hit_count = 0
        self.miss_count = 0
        self.access_frequency: Dict[str, int] = {}
        self.last_access: Dict[str, datetime] = {}
    
    def record_hit(self, key: str):
        """Record cache hit."""
        self.hit_count += 1
        self.access_frequency[key] = self.access_frequency.get(key, 0) + 1
        self.last_access[key] = datetime.now()
    
    def record_miss(self, key: str):
        """Record cache miss."""
        self.miss_count += 1
    
    def get_eviction_candidates(
        self,
        cache_items: Dict[str, Any],
        count: int = 10
    ) -> List[str]:
        """
        Get candidates for eviction based on access patterns.
        
        Args:
            cache_items: Current cache items
            count: Number of candidates to return
        
        Returns:
            List of keys to evict
        """
        # Score items based on:
        # - Access frequency
        # - Recency of access
        # - Size
        
        candidates = []
        for key, value in cache_items.items():
            frequency = self.access_frequency.get(key, 0)
            last_access = self.last_access.get(key, datetime.min)
            
            # Higher score = higher priority for eviction
            recency_score = (
                (datetime.now() - last_access).total_seconds()
            ) / 3600  # Score based on hours since last access
            
            frequency_score = 1.0 / max(1, frequency)  # Inverse frequency
            
            score = recency_score * 0.7 + frequency_score * 0.3
            
            candidates.append((key, score))
        
        # Sort by score (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return [key for key, score in candidates[:count]]
    
    def get_hit_ratio(self) -> float:
        """Get cache hit ratio."""
        total = self.hit_count + self.miss_count
        if total == 0:
            return 0.0
        return self.hit_count / total


# Global instances
cache_compressor = CacheCompressor()
memory_optimizing_cache = MemoryOptimizingCache()
adaptive_eviction = AdaptiveEvictionPolicy()
