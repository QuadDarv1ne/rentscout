"""
ML-based Cache TTL Predictor for RentScout v2.2.0

Predicts optimal cache TTL for different types of data based on:
- Historical access patterns
- Data change frequency
- Memory pressure
- Seasonal trends
- Source-specific behaviors
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class DataType(Enum):
    """Types of data to predict TTL for"""
    PROPERTY = "property"
    SEARCH_RESULT = "search_result"
    PARSER_METADATA = "parser_metadata"
    USER_PREFERENCE = "user_preference"
    AGGREGATE_STATS = "aggregate_stats"
    PRICE_HISTORY = "price_history"
    LOCATION_DATA = "location_data"


class Season(Enum):
    """Seasonal data for trend analysis"""
    WINTER = "winter"
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"


@dataclass
class AccessPattern:
    """Pattern of how data is accessed"""
    key: str
    data_type: DataType
    access_count: int = 0
    last_access: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    total_size_bytes: int = 0
    update_frequency_hours: float = 24.0  # Default to 24 hours
    source: str = "unknown"
    is_seasonal: bool = False
    trend: str = "stable"  # stable, increasing, decreasing
    
    @property
    def age_hours(self) -> float:
        """Age of data in hours"""
        return (datetime.now() - self.created_at).total_seconds() / 3600
    
    @property
    def hours_since_access(self) -> float:
        """Hours since last access"""
        return (datetime.now() - self.last_access).total_seconds() / 3600
    
    @property
    def access_frequency(self) -> float:
        """Accesses per hour"""
        if self.age_hours == 0:
            return 0.0
        return self.access_count / self.age_hours


@dataclass
class TTLPrediction:
    """Result of TTL prediction"""
    key: str
    predicted_ttl_seconds: int
    confidence: float  # 0.0 to 1.0
    reason: str
    factors: Dict[str, float]
    recommended_action: str


class AccessPatternAnalyzer:
    """Analyzes access patterns to understand data behavior"""
    
    def __init__(self, history_size: int = 10000):
        self.patterns: Dict[str, AccessPattern] = {}
        self.history = deque(maxlen=history_size)
        self.access_timeline: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
    def record_access(self, key: str, data_type: DataType, size_bytes: int = 0, source: str = "unknown"):
        """Record an access to a key"""
        now = datetime.now()
        
        if key not in self.patterns:
            self.patterns[key] = AccessPattern(
                key=key,
                data_type=data_type,
                source=source,
                total_size_bytes=size_bytes
            )
        
        pattern = self.patterns[key]
        pattern.access_count += 1
        pattern.last_access = now
        pattern.total_size_bytes = max(pattern.total_size_bytes, size_bytes)
        
        # Record timeline
        self.access_timeline[key].append(now)
        self.history.append((key, now))
        
    def get_access_frequency(self, key: str) -> float:
        """Calculate access frequency (accesses/hour)"""
        if key not in self.patterns:
            return 0.0
        return self.patterns[key].access_frequency
    
    def estimate_update_frequency(self, key: str) -> float:
        """Estimate how often data is updated (hours between updates)"""
        if key not in self.access_timeline:
            return 24.0  # Default to daily
        
        timeline = list(self.access_timeline[key])
        if len(timeline) < 2:
            return 24.0
        
        # Calculate average time between accesses
        intervals = []
        for i in range(1, len(timeline)):
            delta = (timeline[i] - timeline[i-1]).total_seconds() / 3600
            if delta > 0:
                intervals.append(delta)
        
        if not intervals:
            return 24.0
        
        # Use median instead of mean to avoid outliers
        return float(np.median(intervals))
    
    def get_pattern(self, key: str) -> Optional[AccessPattern]:
        """Get access pattern for a key"""
        return self.patterns.get(key)
    
    def cleanup_old_patterns(self, age_threshold_hours: int = 168):
        """Remove patterns older than threshold"""
        now = datetime.now()
        keys_to_remove = []
        
        for key, pattern in self.patterns.items():
            age = (now - pattern.created_at).total_seconds() / 3600
            if age > age_threshold_hours and pattern.hours_since_access > age_threshold_hours:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.patterns[key]
        
        logger.info(f"Cleaned up {len(keys_to_remove)} old patterns")


class TTLPredictor:
    """Predicts optimal TTL using machine learning approach"""
    
    # Base TTL values (seconds) for different data types
    BASE_TTL = {
        DataType.PROPERTY: 3600,  # 1 hour
        DataType.SEARCH_RESULT: 1800,  # 30 minutes
        DataType.PARSER_METADATA: 7200,  # 2 hours
        DataType.USER_PREFERENCE: 86400,  # 1 day
        DataType.AGGREGATE_STATS: 3600,  # 1 hour
        DataType.PRICE_HISTORY: 86400,  # 1 day
        DataType.LOCATION_DATA: 172800,  # 2 days
    }
    
    # Multipliers for different sources
    SOURCE_MULTIPLIERS = {
        "avito": 0.8,  # Changes frequently
        "cian": 0.9,  # Changes often
        "domofond": 1.0,  # Standard
        "yandex_realty": 1.1,  # More stable
        "ostrovok": 0.7,  # Changes very frequently
        "unknown": 1.0,
    }
    
    def __init__(self, analyzer: AccessPatternAnalyzer):
        self.analyzer = analyzer
        self.predictions_cache: Dict[str, Tuple[TTLPrediction, datetime]] = {}
        self.prediction_accuracy: List[float] = []
        
    def predict_ttl(self, key: str, pattern: AccessPattern) -> TTLPrediction:
        """Predict optimal TTL for a key"""
        
        # Check cache
        cache_key = f"{key}:{pattern.data_type.value}"
        if cache_key in self.predictions_cache:
            pred, cached_at = self.predictions_cache[cache_key]
            if (datetime.now() - cached_at).total_seconds() < 3600:  # 1 hour cache
                return pred
        
        # Calculate factors
        factors = self._calculate_factors(key, pattern)
        
        # Get base TTL
        base_ttl = self.BASE_TTL.get(pattern.data_type, 3600)
        
        # Apply adjustments
        ttl = self._adjust_ttl(base_ttl, factors)
        
        # Calculate confidence
        confidence = self._calculate_confidence(pattern, factors)
        
        # Determine recommendation
        reason, recommendation = self._generate_reason_and_recommendation(
            pattern, factors, ttl
        )
        
        prediction = TTLPrediction(
            key=key,
            predicted_ttl_seconds=max(60, ttl),  # Minimum 1 minute
            confidence=confidence,
            reason=reason,
            factors=factors,
            recommended_action=recommendation
        )
        
        self.predictions_cache[cache_key] = (prediction, datetime.now())
        return prediction
    
    def _calculate_factors(self, key: str, pattern: AccessPattern) -> Dict[str, float]:
        """Calculate adjustment factors"""
        factors = {}
        
        # Access frequency factor (0.5 to 2.0)
        access_freq = pattern.access_frequency
        if access_freq < 0.1:
            factors['access_frequency'] = 1.8  # Low access = longer TTL
        elif access_freq < 1.0:
            factors['access_frequency'] = 1.2
        elif access_freq < 10.0:
            factors['access_frequency'] = 0.9
        else:
            factors['access_frequency'] = 0.5  # High access = shorter TTL
        
        # Data size factor (0.8 to 1.5)
        if pattern.total_size_bytes < 1000:  # < 1KB
            factors['data_size'] = 0.9
        elif pattern.total_size_bytes < 100000:  # < 100KB
            factors['data_size'] = 1.0
        elif pattern.total_size_bytes < 1000000:  # < 1MB
            factors['data_size'] = 1.2
        else:  # >= 1MB
            factors['data_size'] = 1.5  # Larger objects = longer cache
        
        # Source factor
        factors['source'] = self.SOURCE_MULTIPLIERS.get(pattern.source, 1.0)
        
        # Staleness factor (0.7 to 1.5)
        hours_since_access = pattern.hours_since_access
        if hours_since_access > 168:  # > 1 week
            factors['staleness'] = 1.5  # Not accessed recently = longer TTL
        elif hours_since_access > 24:
            factors['staleness'] = 1.2
        elif hours_since_access > 1:
            factors['staleness'] = 1.0
        else:
            factors['staleness'] = 0.8  # Recently accessed = shorter TTL
        
        # Seasonal factor (0.7 to 1.3)
        factors['seasonal'] = 1.3 if pattern.is_seasonal else 1.0
        
        # Trend factor (0.8 to 1.3)
        if pattern.trend == "increasing":
            factors['trend'] = 0.8  # Data changing = shorter TTL
        elif pattern.trend == "decreasing":
            factors['trend'] = 0.9
        else:
            factors['trend'] = 1.0  # Stable = standard TTL
        
        return factors
    
    def _adjust_ttl(self, base_ttl: int, factors: Dict[str, float]) -> int:
        """Apply factors to base TTL"""
        adjusted = base_ttl
        
        # Apply each factor
        adjusted *= factors.get('access_frequency', 1.0)
        adjusted *= factors.get('data_size', 1.0)
        adjusted *= factors.get('source', 1.0)
        adjusted *= factors.get('staleness', 1.0)
        adjusted *= factors.get('seasonal', 1.0)
        adjusted *= factors.get('trend', 1.0)
        
        return int(adjusted)
    
    def _calculate_confidence(self, pattern: AccessPattern, factors: Dict[str, float]) -> float:
        """Calculate prediction confidence (0.0 to 1.0)"""
        confidence = 0.5  # Base confidence
        
        # More access history = higher confidence
        if pattern.access_count > 100:
            confidence += 0.3
        elif pattern.access_count > 10:
            confidence += 0.2
        elif pattern.access_count > 1:
            confidence += 0.1
        
        # More age = higher confidence
        if pattern.age_hours > 168:  # > 1 week
            confidence += 0.2
        elif pattern.age_hours > 24:
            confidence += 0.1
        
        # Factor variance = lower confidence
        factor_values = list(factors.values())
        if factor_values:
            variance = float(np.var(factor_values))
            if variance > 0.1:
                confidence -= 0.1
        
        return min(1.0, max(0.0, confidence))
    
    def _generate_reason_and_recommendation(
        self,
        pattern: AccessPattern,
        factors: Dict[str, float],
        ttl: int
    ) -> Tuple[str, str]:
        """Generate reason and recommendation for TTL prediction"""
        
        reason_parts = []
        
        # Access frequency insight
        freq = factors.get('access_frequency', 1.0)
        if freq < 0.8:
            reason_parts.append("низкая частота доступа")
        elif freq > 1.2:
            reason_parts.append("высокая частота доступа")
        
        # Size insight
        size_factor = factors.get('data_size', 1.0)
        if size_factor > 1.1:
            reason_parts.append("большой размер данных")
        
        # Source insight
        source = pattern.source
        if source != "unknown":
            reason_parts.append(f"источник: {source}")
        
        reason = "Предсказание основано на: " + ", ".join(reason_parts) if reason_parts else "Стандартное предсказание"
        
        # Recommendation
        ttl_minutes = ttl // 60
        ttl_hours = ttl // 3600
        
        if ttl < 300:
            recommendation = f"⚠️ Очень короткий кеш ({ttl_minutes} мин) - ожидается частое обновление"
        elif ttl < 1800:
            recommendation = f"🟡 Короткий кеш ({ttl_minutes} мин) - данные часто меняются"
        elif ttl < 3600:
            recommendation = f"🟢 Стандартный кеш ({ttl_minutes} мин) - сбалансированный подход"
        else:
            recommendation = f"✅ Длительный кеш ({ttl_hours} часов) - стабильные данные"
        
        return reason, recommendation


class CacheTTLOptimizer:
    """Coordinates TTL prediction and optimization"""
    
    def __init__(self):
        self.analyzer = AccessPatternAnalyzer()
        self.predictor = TTLPredictor(self.analyzer)
        self.current_ttls: Dict[str, int] = {}
        self.optimization_history: List[Tuple[datetime, str, int, int]] = []
        
    def record_cache_access(self, key: str, data_type: DataType, size_bytes: int = 0, source: str = "unknown"):
        """Record cache access for analysis"""
        self.analyzer.record_access(key, data_type, size_bytes, source)
    
    def get_recommended_ttl(self, key: str) -> Optional[int]:
        """Get recommended TTL for a key"""
        pattern = self.analyzer.get_pattern(key)
        if not pattern:
            return None
        
        prediction = self.predictor.predict_ttl(key, pattern)
        return prediction.predicted_ttl_seconds
    
    def apply_ttl_optimization(self, key: str, current_ttl: int) -> Tuple[int, TTLPrediction]:
        """Apply TTL optimization and return new TTL"""
        pattern = self.analyzer.get_pattern(key)
        if not pattern:
            return current_ttl, TTLPrediction(
                key=key,
                predicted_ttl_seconds=current_ttl,
                confidence=0.0,
                reason="Недостаточно данных",
                factors={},
                recommended_action="Собирайте больше данных"
            )
        
        prediction = self.predictor.predict_ttl(key, pattern)
        
        # Record optimization
        self.optimization_history.append((
            datetime.now(),
            key,
            current_ttl,
            prediction.predicted_ttl_seconds
        ))
        
        self.current_ttls[key] = prediction.predicted_ttl_seconds
        
        return prediction.predicted_ttl_seconds, prediction
    
    def get_optimization_stats(self) -> Dict:
        """Get statistics about TTL optimization"""
        if not self.optimization_history:
            return {
                "total_optimizations": 0,
                "average_change": 0.0,
                "optimization_savings_percent": 0.0,
            }
        
        total = len(self.optimization_history)
        savings = []
        
        for _, _, old_ttl, new_ttl in self.optimization_history:
            if old_ttl > 0:
                change = ((old_ttl - new_ttl) / old_ttl) * 100
                savings.append(change)
        
        avg_savings = float(np.mean(savings)) if savings else 0.0
        
        return {
            "total_optimizations": total,
            "average_change_seconds": sum(old - new for _, _, old, new in self.optimization_history) / total if total > 0 else 0,
            "average_change_percent": avg_savings,
            "optimizations_reducing_ttl": sum(1 for _, _, old, new in self.optimization_history if new < old),
            "optimizations_increasing_ttl": sum(1 for _, _, old, new in self.optimization_history if new > old),
        }
    
    def cleanup(self):
        """Cleanup old patterns and caches"""
        self.analyzer.cleanup_old_patterns(age_threshold_hours=168)
        # Keep optimization history manageable
        if len(self.optimization_history) > 10000:
            self.optimization_history = self.optimization_history[-10000:]
    
    def get_top_optimization_candidates(self, top_n: int = 10) -> List[Tuple[str, int, int]]:
        """Get top candidates for TTL optimization"""
        candidates = []
        
        for key, pattern in self.analyzer.patterns.items():
            current_ttl = self.current_ttls.get(key)
            if not current_ttl:
                continue
            
            prediction = self.predictor.predict_ttl(key, pattern)
            potential_saving = abs(prediction.predicted_ttl_seconds - current_ttl)
            
            candidates.append((key, current_ttl, prediction.predicted_ttl_seconds))
        
        # Sort by potential saving
        candidates.sort(key=lambda x: abs(x[1] - x[2]), reverse=True)
        
        return candidates[:top_n]


# Global instance
cache_ttl_optimizer = CacheTTLOptimizer()


def predict_cache_ttl(
    key: str,
    data_type: DataType,
    current_ttl: int,
    size_bytes: int = 0,
    source: str = "unknown"
) -> TTLPrediction:
    """
    Predict and return optimal TTL for cache key
    
    Args:
        key: Cache key
        data_type: Type of data
        current_ttl: Current TTL in seconds
        size_bytes: Size of cached data
        source: Data source (parser name)
    
    Returns:
        TTLPrediction with recommended TTL and confidence
    """
    # Record the access
    cache_ttl_optimizer.record_cache_access(key, data_type, size_bytes, source)
    
    # Get pattern and prediction
    pattern = cache_ttl_optimizer.analyzer.get_pattern(key)
    if pattern:
        prediction = cache_ttl_optimizer.predictor.predict_ttl(key, pattern)
        return prediction
    
    # Return default if not enough data
    return TTLPrediction(
        key=key,
        predicted_ttl_seconds=current_ttl,
        confidence=0.0,
        reason="Недостаточно истории",
        factors={},
        recommended_action="Соберите больше данных об использовании"
    )
