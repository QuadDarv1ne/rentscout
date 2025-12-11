"""
Auto-Scaling Engine for RentScout v2.2.0

Automatically recommends and manages resource scaling based on:
- CPU and memory utilization
- Request queue depth
- Parser throughput
- Database connection pool
- Cache hit ratio
- Active connections
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)


class ScalingAction(Enum):
    """Type of scaling action"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    SCALE_OUT = "scale_out"  # Add more instances
    SCALE_IN = "scale_in"    # Remove instances
    NO_ACTION = "no_action"


class ResourceType(Enum):
    """Type of resource to scale"""
    CPU = "cpu"
    MEMORY = "memory"
    PARSER_WORKERS = "parser_workers"
    DATABASE_CONNECTIONS = "database_connections"
    API_THREADS = "api_threads"
    CACHE_SIZE = "cache_size"


class ScalingMetric(Enum):
    """Metrics used for scaling decisions"""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    REQUEST_QUEUE = "request_queue"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    CACHE_HIT_RATIO = "cache_hit_ratio"
    DATABASE_CONNECTIONS = "database_connections"
    ACTIVE_PARSERS = "active_parsers"


@dataclass
class MetricSnapshot:
    """Snapshot of a metric at a point in time"""
    timestamp: datetime = field(default_factory=datetime.now)
    value: float = 0.0
    
    @property
    def age_seconds(self) -> float:
        """Age of metric in seconds"""
        return (datetime.now() - self.timestamp).total_seconds()


@dataclass
class ResourceConfig:
    """Configuration for a resource"""
    resource_type: ResourceType
    current_value: float
    min_value: float
    max_value: float
    scale_up_threshold: float
    scale_down_threshold: float
    scale_up_cooldown_seconds: int = 300  # 5 minutes
    scale_down_cooldown_seconds: int = 600  # 10 minutes
    last_scale_up_time: Optional[datetime] = None
    last_scale_down_time: Optional[datetime] = None
    
    def can_scale_up(self) -> bool:
        """Check if can scale up based on cooldown"""
        if not self.last_scale_up_time:
            return True
        elapsed = (datetime.now() - self.last_scale_up_time).total_seconds()
        return elapsed >= self.scale_up_cooldown_seconds
    
    def can_scale_down(self) -> bool:
        """Check if can scale down based on cooldown"""
        if not self.last_scale_down_time:
            return True
        elapsed = (datetime.now() - self.last_scale_down_time).total_seconds()
        return elapsed >= self.scale_down_cooldown_seconds


@dataclass
class ScalingRecommendation:
    """Recommendation for scaling action"""
    resource_type: ResourceType
    action: ScalingAction
    current_value: float
    recommended_value: float
    reason: str
    metrics_involved: List[str]
    confidence: float  # 0.0 to 1.0
    estimated_improvement: float  # Expected % improvement
    cost_impact: str  # "low", "medium", "high"
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """Collects and analyzes metrics for scaling decisions"""
    
    def __init__(self, history_size: int = 360):  # 1 hour at 10s intervals
        self.metrics: Dict[ScalingMetric, deque] = {
            metric: deque(maxlen=history_size)
            for metric in ScalingMetric
        }
    
    def record_metric(self, metric_type: ScalingMetric, value: float):
        """Record a metric value"""
        self.metrics[metric_type].append(MetricSnapshot(value=value))
    
    def get_metric_history(self, metric_type: ScalingMetric, seconds: int = 300) -> List[float]:
        """Get metric history for last N seconds"""
        cutoff = datetime.now() - timedelta(seconds=seconds)
        return [
            m.value for m in self.metrics[metric_type]
            if m.timestamp >= cutoff
        ]
    
    def get_average(self, metric_type: ScalingMetric, seconds: int = 60) -> float:
        """Get average value for metric over time window"""
        values = self.get_metric_history(metric_type, seconds)
        return float(np.mean(values)) if values else 0.0
    
    def get_percentile(self, metric_type: ScalingMetric, percentile: float, seconds: int = 60) -> float:
        """Get percentile value for metric"""
        values = self.get_metric_history(metric_type, seconds)
        return float(np.percentile(values, percentile)) if values else 0.0
    
    def get_trend(self, metric_type: ScalingMetric, seconds: int = 300) -> str:
        """Get trend direction for metric"""
        values = self.get_metric_history(metric_type, seconds)
        if len(values) < 2:
            return "stable"
        
        # Simple linear regression
        x = np.arange(len(values))
        if len(x) > 1 and len(values) > 1:
            slope = np.polyfit(x, values, 1)[0]
            if slope > 0.1:
                return "increasing"
            elif slope < -0.1:
                return "decreasing"
        
        return "stable"
    
    def get_volatility(self, metric_type: ScalingMetric, seconds: int = 300) -> float:
        """Get volatility (std deviation) of metric"""
        values = self.get_metric_history(metric_type, seconds)
        return float(np.std(values)) if len(values) > 1 else 0.0


class AutoScalingEngine:
    """Main auto-scaling decision engine"""
    
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.resource_configs: Dict[ResourceType, ResourceConfig] = {}
        self.scaling_history: List[ScalingRecommendation] = []
        self.max_history_size = 1000
        self._init_default_configs()
    
    def _init_default_configs(self):
        """Initialize default resource configurations"""
        # CPU scaling
        self.resource_configs[ResourceType.CPU] = ResourceConfig(
            resource_type=ResourceType.CPU,
            current_value=30.0,
            min_value=10.0,
            max_value=80.0,
            scale_up_threshold=70.0,
            scale_down_threshold=20.0
        )
        
        # Memory scaling
        self.resource_configs[ResourceType.MEMORY] = ResourceConfig(
            resource_type=ResourceType.MEMORY,
            current_value=50.0,
            min_value=512,  # MB
            max_value=8192,
            scale_up_threshold=80.0,
            scale_down_threshold=30.0
        )
        
        # Parser workers
        self.resource_configs[ResourceType.PARSER_WORKERS] = ResourceConfig(
            resource_type=ResourceType.PARSER_WORKERS,
            current_value=4.0,
            min_value=1.0,
            max_value=32.0,
            scale_up_threshold=85.0,
            scale_down_threshold=25.0,
            scale_up_cooldown_seconds=300
        )
        
        # Database connections
        self.resource_configs[ResourceType.DATABASE_CONNECTIONS] = ResourceConfig(
            resource_type=ResourceType.DATABASE_CONNECTIONS,
            current_value=10.0,
            min_value=5.0,
            max_value=100.0,
            scale_up_threshold=80.0,
            scale_down_threshold=20.0
        )
        
        # API threads
        self.resource_configs[ResourceType.API_THREADS] = ResourceConfig(
            resource_type=ResourceType.API_THREADS,
            current_value=8.0,
            min_value=2.0,
            max_value=64.0,
            scale_up_threshold=80.0,
            scale_down_threshold=20.0
        )
        
        # Cache size
        self.resource_configs[ResourceType.CACHE_SIZE] = ResourceConfig(
            resource_type=ResourceType.CACHE_SIZE,
            current_value=512.0,  # MB
            min_value=128.0,
            max_value=4096.0,
            scale_up_threshold=85.0,
            scale_down_threshold=30.0
        )
    
    def record_metric(self, metric_type: ScalingMetric, value: float):
        """Record system metric"""
        self.metrics_collector.record_metric(metric_type, value)
    
    def analyze_and_recommend(self) -> List[ScalingRecommendation]:
        """Analyze metrics and generate scaling recommendations"""
        recommendations = []
        
        # Analyze CPU usage
        cpu_rec = self._analyze_cpu_scaling()
        if cpu_rec:
            recommendations.append(cpu_rec)
        
        # Analyze memory usage
        mem_rec = self._analyze_memory_scaling()
        if mem_rec:
            recommendations.append(mem_rec)
        
        # Analyze parser workload
        parser_rec = self._analyze_parser_scaling()
        if parser_rec:
            recommendations.append(parser_rec)
        
        # Analyze database connections
        db_rec = self._analyze_database_scaling()
        if db_rec:
            recommendations.append(db_rec)
        
        # Analyze cache efficiency
        cache_rec = self._analyze_cache_scaling()
        if cache_rec:
            recommendations.append(cache_rec)
        
        # Record recommendations
        for rec in recommendations:
            self.scaling_history.append(rec)
        
        # Keep history manageable
        if len(self.scaling_history) > self.max_history_size:
            self.scaling_history = self.scaling_history[-self.max_history_size:]
        
        return recommendations
    
    def _analyze_cpu_scaling(self) -> Optional[ScalingRecommendation]:
        """Analyze CPU usage for scaling"""
        config = self.resource_configs[ResourceType.CPU]
        avg_cpu = self.metrics_collector.get_average(ScalingMetric.CPU_USAGE, 300)
        p95_cpu = self.metrics_collector.get_percentile(ScalingMetric.CPU_USAGE, 95, 300)
        trend = self.metrics_collector.get_trend(ScalingMetric.CPU_USAGE, 300)
        
        if p95_cpu >= config.scale_up_threshold and config.can_scale_up():
            config.last_scale_up_time = datetime.now()
            return ScalingRecommendation(
                resource_type=ResourceType.CPU,
                action=ScalingAction.SCALE_UP,
                current_value=avg_cpu,
                recommended_value=min(avg_cpu * 1.5, 100.0),
                reason=f"High CPU usage: P95={p95_cpu:.1f}%, Trend={trend}",
                metrics_involved=["cpu_usage", "response_time"],
                confidence=0.85 if trend == "increasing" else 0.7,
                estimated_improvement=15.0,
                cost_impact="medium"
            )
        
        elif avg_cpu <= config.scale_down_threshold and config.can_scale_down():
            config.last_scale_down_time = datetime.now()
            return ScalingRecommendation(
                resource_type=ResourceType.CPU,
                action=ScalingAction.SCALE_DOWN,
                current_value=avg_cpu,
                recommended_value=max(avg_cpu * 0.8, 10.0),
                reason=f"Low CPU usage: Avg={avg_cpu:.1f}%, Trend={trend}",
                metrics_involved=["cpu_usage"],
                confidence=0.6 if trend == "stable" else 0.4,
                estimated_improvement=-10.0,
                cost_impact="low"
            )
        
        return None
    
    def _analyze_memory_scaling(self) -> Optional[ScalingRecommendation]:
        """Analyze memory usage for scaling"""
        config = self.resource_configs[ResourceType.MEMORY]
        avg_mem = self.metrics_collector.get_average(ScalingMetric.MEMORY_USAGE, 300)
        
        if avg_mem >= config.scale_up_threshold and config.can_scale_up():
            config.last_scale_up_time = datetime.now()
            return ScalingRecommendation(
                resource_type=ResourceType.MEMORY,
                action=ScalingAction.SCALE_UP,
                current_value=avg_mem,
                recommended_value=min(config.current_value * 1.5, config.max_value),
                reason=f"Memory pressure: {avg_mem:.1f}%",
                metrics_involved=["memory_usage", "cache_size"],
                confidence=0.8,
                estimated_improvement=20.0,
                cost_impact="medium"
            )
        
        elif avg_mem <= config.scale_down_threshold and config.can_scale_down():
            config.last_scale_down_time = datetime.now()
            return ScalingRecommendation(
                resource_type=ResourceType.MEMORY,
                action=ScalingAction.SCALE_DOWN,
                current_value=avg_mem,
                recommended_value=max(config.current_value * 0.8, config.min_value),
                reason=f"Low memory usage: {avg_mem:.1f}%",
                metrics_involved=["memory_usage"],
                confidence=0.6,
                estimated_improvement=-15.0,
                cost_impact="low"
            )
        
        return None
    
    def _analyze_parser_scaling(self) -> Optional[ScalingRecommendation]:
        """Analyze parser workload for scaling"""
        config = self.resource_configs[ResourceType.PARSER_WORKERS]
        active_parsers = self.metrics_collector.get_average(ScalingMetric.ACTIVE_PARSERS, 300)
        queue_depth = self.metrics_collector.get_average(ScalingMetric.REQUEST_QUEUE, 300)
        
        if (active_parsers / config.current_value > 0.8 or queue_depth > 50) and config.can_scale_up():
            config.last_scale_up_time = datetime.now()
            return ScalingRecommendation(
                resource_type=ResourceType.PARSER_WORKERS,
                action=ScalingAction.SCALE_OUT,
                current_value=config.current_value,
                recommended_value=min(config.current_value + 2, config.max_value),
                reason=f"Parser queue building: {queue_depth:.0f} items, {active_parsers:.0f}/{config.current_value} workers busy",
                metrics_involved=["active_parsers", "request_queue"],
                confidence=0.85,
                estimated_improvement=25.0,
                cost_impact="medium"
            )
        
        elif queue_depth < 5 and config.current_value > config.min_value and config.can_scale_down():
            config.last_scale_down_time = datetime.now()
            return ScalingRecommendation(
                resource_type=ResourceType.PARSER_WORKERS,
                action=ScalingAction.SCALE_IN,
                current_value=config.current_value,
                recommended_value=max(config.current_value - 1, config.min_value),
                reason=f"Low parser load: Queue={queue_depth:.0f}, Active={active_parsers:.0f}",
                metrics_involved=["request_queue", "active_parsers"],
                confidence=0.7,
                estimated_improvement=-10.0,
                cost_impact="low"
            )
        
        return None
    
    def _analyze_database_scaling(self) -> Optional[ScalingRecommendation]:
        """Analyze database connection pool for scaling"""
        config = self.resource_configs[ResourceType.DATABASE_CONNECTIONS]
        connections = self.metrics_collector.get_average(ScalingMetric.DATABASE_CONNECTIONS, 300)
        
        if connections >= config.scale_up_threshold and config.can_scale_up():
            config.last_scale_up_time = datetime.now()
            return ScalingRecommendation(
                resource_type=ResourceType.DATABASE_CONNECTIONS,
                action=ScalingAction.SCALE_UP,
                current_value=config.current_value,
                recommended_value=min(config.current_value * 1.5, config.max_value),
                reason=f"Database pool exhaustion: {connections:.0f}/{config.current_value} connections",
                metrics_involved=["database_connections"],
                confidence=0.9,
                estimated_improvement=30.0,
                cost_impact="low"
            )
        
        return None
    
    def _analyze_cache_scaling(self) -> Optional[ScalingRecommendation]:
        """Analyze cache efficiency for scaling"""
        config = self.resource_configs[ResourceType.CACHE_SIZE]
        hit_ratio = self.metrics_collector.get_average(ScalingMetric.CACHE_HIT_RATIO, 300)
        
        if hit_ratio < 50.0 and config.can_scale_up():
            config.last_scale_up_time = datetime.now()
            return ScalingRecommendation(
                resource_type=ResourceType.CACHE_SIZE,
                action=ScalingAction.SCALE_UP,
                current_value=config.current_value,
                recommended_value=min(config.current_value * 1.5, config.max_value),
                reason=f"Low cache hit ratio: {hit_ratio:.1f}%",
                metrics_involved=["cache_hit_ratio"],
                confidence=0.75,
                estimated_improvement=20.0,
                cost_impact="medium"
            )
        
        elif hit_ratio > 85.0 and config.current_value > config.min_value and config.can_scale_down():
            config.last_scale_down_time = datetime.now()
            return ScalingRecommendation(
                resource_type=ResourceType.CACHE_SIZE,
                action=ScalingAction.SCALE_DOWN,
                current_value=config.current_value,
                recommended_value=max(config.current_value * 0.9, config.min_value),
                reason=f"High cache efficiency: {hit_ratio:.1f}% hit ratio",
                metrics_involved=["cache_hit_ratio"],
                confidence=0.7,
                estimated_improvement=-5.0,
                cost_impact="low"
            )
        
        return None
    
    def get_scaling_statistics(self) -> Dict:
        """Get statistics about scaling actions"""
        if not self.scaling_history:
            return {
                "total_recommendations": 0,
                "scale_up_count": 0,
                "scale_down_count": 0,
                "scale_out_count": 0,
                "scale_in_count": 0,
            }
        
        return {
            "total_recommendations": len(self.scaling_history),
            "scale_up_count": sum(1 for r in self.scaling_history if r.action == ScalingAction.SCALE_UP),
            "scale_down_count": sum(1 for r in self.scaling_history if r.action == ScalingAction.SCALE_DOWN),
            "scale_out_count": sum(1 for r in self.scaling_history if r.action == ScalingAction.SCALE_OUT),
            "scale_in_count": sum(1 for r in self.scaling_history if r.action == ScalingAction.SCALE_IN),
            "average_confidence": np.mean([r.confidence for r in self.scaling_history]),
            "estimated_total_improvement": sum(r.estimated_improvement for r in self.scaling_history),
        }
    
    def get_recent_recommendations(self, count: int = 10) -> List[ScalingRecommendation]:
        """Get most recent scaling recommendations"""
        return self.scaling_history[-count:]


# Global instance
auto_scaling_engine = AutoScalingEngine()


def recommend_scaling() -> List[ScalingRecommendation]:
    """Get scaling recommendations based on current metrics"""
    return auto_scaling_engine.analyze_and_recommend()
