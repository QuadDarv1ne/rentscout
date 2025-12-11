"""
Performance Profiling Tools for RentScout v2.2.0

Provides detailed performance analysis:
- Function profiling
- Memory profiling
- Call stack analysis
- Bottleneck detection
- Performance benchmarking
- Comparative profiling
"""

import logging
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from contextlib import contextmanager
from collections import defaultdict, deque
import functools

logger = logging.getLogger(__name__)


class ProfileType(Enum):
    """Type of profiling"""
    CPU = "cpu"
    MEMORY = "memory"
    IO = "io"
    NETWORK = "network"
    DATABASE = "database"


@dataclass
class FunctionProfile:
    """Profile of a function"""
    function_name: str
    module_name: str
    call_count: int = 0
    total_time: float = 0.0  # seconds
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    calls_per_second: float = 0.0
    memory_used: int = 0  # bytes
    memory_peak: int = 0
    first_call: Optional[datetime] = None
    last_call: Optional[datetime] = None
    
    @property
    def duration_seconds(self) -> float:
        """Duration since first call"""
        if self.first_call and self.last_call:
            return (self.last_call - self.first_call).total_seconds()
        return 0.0
    
    def update(self, exec_time: float, memory_delta: int = 0):
        """Update profile with new measurement"""
        self.call_count += 1
        self.total_time += exec_time
        self.min_time = min(self.min_time, exec_time)
        self.max_time = max(self.max_time, exec_time)
        self.avg_time = self.total_time / self.call_count
        self.memory_used += memory_delta
        self.memory_peak = max(self.memory_peak, self.memory_used)
        
        now = datetime.now()
        if not self.first_call:
            self.first_call = now
        self.last_call = now
        
        if self.duration_seconds > 0:
            self.calls_per_second = self.call_count / self.duration_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'function_name': self.function_name,
            'module_name': self.module_name,
            'call_count': self.call_count,
            'total_time': round(self.total_time, 4),
            'min_time': round(self.min_time if self.min_time != float('inf') else 0, 4),
            'max_time': round(self.max_time, 4),
            'avg_time': round(self.avg_time, 4),
            'calls_per_second': round(self.calls_per_second, 2),
            'memory_used': self.memory_used,
            'memory_peak': self.memory_peak,
        }


@dataclass
class CallStackFrame:
    """Single frame in call stack"""
    function_name: str
    file_name: str
    line_number: int
    depth: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceBottleneck:
    """Identified performance bottleneck"""
    function_name: str
    bottleneck_type: str  # "time", "memory", "io", etc.
    severity: str  # "critical", "high", "medium", "low"
    current_value: float
    baseline_value: float
    deviation_percent: float
    recommendation: str
    timestamp: datetime = field(default_factory=datetime.now)


class FunctionProfiler:
    """Profiles individual functions"""
    
    def __init__(self, history_size: int = 1000):
        self.profiles: Dict[str, FunctionProfile] = {}
        self.call_history: deque = deque(maxlen=history_size)
    
    def profile_function(self, func: Callable) -> Callable:
        """Decorator to profile function execution"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            profile_key = f"{func.__module__}.{func.__name__}"
            
            # Get starting memory
            tracemalloc.start()
            start_memory = tracemalloc.get_traced_memory()[0]
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Record profile
                end_time = time.time()
                end_memory = tracemalloc.get_traced_memory()[0]
                tracemalloc.stop()
                
                exec_time = end_time - start_time
                memory_delta = end_memory - start_memory
                
                if profile_key not in self.profiles:
                    self.profiles[profile_key] = FunctionProfile(
                        function_name=func.__name__,
                        module_name=func.__module__
                    )
                
                self.profiles[profile_key].update(exec_time, memory_delta)
                self.call_history.append({
                    'function': profile_key,
                    'time': exec_time,
                    'memory': memory_delta,
                    'timestamp': datetime.now()
                })
        
        return wrapper
    
    def get_profile(self, function_key: str) -> Optional[FunctionProfile]:
        """Get profile for function"""
        return self.profiles.get(function_key)
    
    def get_slowest_functions(self, limit: int = 10) -> List[FunctionProfile]:
        """Get slowest functions by total time"""
        profiles = sorted(
            self.profiles.values(),
            key=lambda p: p.total_time,
            reverse=True
        )
        return profiles[:limit]
    
    def get_most_called_functions(self, limit: int = 10) -> List[FunctionProfile]:
        """Get most frequently called functions"""
        profiles = sorted(
            self.profiles.values(),
            key=lambda p: p.call_count,
            reverse=True
        )
        return profiles[:limit]
    
    def get_memory_hogs(self, limit: int = 10) -> List[FunctionProfile]:
        """Get functions using most memory"""
        profiles = sorted(
            self.profiles.values(),
            key=lambda p: p.memory_peak,
            reverse=True
        )
        return profiles[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get profiling statistics"""
        if not self.profiles:
            return {
                'total_functions': 0,
                'total_calls': 0,
                'total_time': 0.0,
                'total_memory': 0,
            }
        
        return {
            'total_functions': len(self.profiles),
            'total_calls': sum(p.call_count for p in self.profiles.values()),
            'total_time': sum(p.total_time for p in self.profiles.values()),
            'total_memory': sum(p.memory_peak for p in self.profiles.values()),
            'avg_calls_per_function': sum(p.call_count for p in self.profiles.values()) / len(self.profiles),
        }


class MemoryProfiler:
    """Profiles memory usage"""
    
    def __init__(self, sample_size: int = 1000):
        self.memory_snapshots: deque = deque(maxlen=sample_size)
        self.peak_memory: int = 0
        self.baseline_memory: int = 0
    
    def take_snapshot(self, label: str = "") -> Dict[str, Any]:
        """Take memory snapshot"""
        tracemalloc.start()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        if not self.baseline_memory:
            self.baseline_memory = current
        
        self.peak_memory = max(self.peak_memory, peak)
        
        snapshot = {
            'label': label,
            'timestamp': datetime.now(),
            'current_memory': current,
            'peak_memory': peak,
            'memory_delta_from_baseline': current - self.baseline_memory,
        }
        
        self.memory_snapshots.append(snapshot)
        return snapshot
    
    def get_memory_trend(self) -> str:
        """Get memory trend direction"""
        if len(self.memory_snapshots) < 2:
            return "insufficient_data"
        
        snapshots = list(self.memory_snapshots)
        mid = len(snapshots) // 2
        
        recent_avg = sum(s['current_memory'] for s in snapshots[mid:]) / len(snapshots[mid:])
        older_avg = sum(s['current_memory'] for s in snapshots[:mid]) / len(snapshots[:mid])
        
        change_percent = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        
        if change_percent > 5:
            return "increasing"
        elif change_percent < -5:
            return "decreasing"
        else:
            return "stable"
    
    def get_memory_summary(self) -> Dict[str, Any]:
        """Get memory summary"""
        if not self.memory_snapshots:
            return {}
        
        snapshots = list(self.memory_snapshots)
        current_mem = snapshots[-1]['current_memory']
        
        return {
            'current_memory_mb': round(current_mem / 1024 / 1024, 2),
            'peak_memory_mb': round(self.peak_memory / 1024 / 1024, 2),
            'baseline_memory_mb': round(self.baseline_memory / 1024 / 1024, 2),
            'trend': self.get_memory_trend(),
            'snapshots_taken': len(snapshots),
        }


class BottleneckDetector:
    """Detects performance bottlenecks"""
    
    def __init__(self):
        self.baselines: Dict[str, float] = {}
        self.detected_bottlenecks: List[PerformanceBottleneck] = []
        self.max_history = 1000
    
    def set_baseline(self, metric_name: str, baseline_value: float):
        """Set performance baseline"""
        self.baselines[metric_name] = baseline_value
    
    def check_metric(
        self,
        metric_name: str,
        current_value: float,
        bottleneck_type: str
    ) -> Optional[PerformanceBottleneck]:
        """Check if metric exceeds baseline"""
        if metric_name not in self.baselines:
            self.baselines[metric_name] = current_value
            return None
        
        baseline = self.baselines[metric_name]
        deviation_percent = ((current_value - baseline) / baseline * 100) if baseline > 0 else 0
        
        # Determine severity
        if deviation_percent > 50:
            severity = "critical"
        elif deviation_percent > 30:
            severity = "high"
        elif deviation_percent > 15:
            severity = "medium"
        else:
            severity = "low"
            return None  # Only report if deviation > 15%
        
        # Generate recommendation
        function_name = metric_name.split('.')[-1]
        recommendation = f"Оптимизируйте {function_name}: текущее значение {current_value:.2f} превышает baseline {baseline:.2f}"
        
        bottleneck = PerformanceBottleneck(
            function_name=metric_name,
            bottleneck_type=bottleneck_type,
            severity=severity,
            current_value=current_value,
            baseline_value=baseline,
            deviation_percent=deviation_percent,
            recommendation=recommendation
        )
        
        self.detected_bottlenecks.append(bottleneck)
        if len(self.detected_bottlenecks) > self.max_history:
            self.detected_bottlenecks = self.detected_bottlenecks[-self.max_history:]
        
        return bottleneck
    
    def get_critical_bottlenecks(self) -> List[PerformanceBottleneck]:
        """Get only critical bottlenecks"""
        return [b for b in self.detected_bottlenecks if b.severity == "critical"]
    
    def get_recent_bottlenecks(self, limit: int = 10) -> List[PerformanceBottleneck]:
        """Get recent bottlenecks"""
        return self.detected_bottlenecks[-limit:]


class PerformanceProfiler:
    """Main performance profiling system"""
    
    def __init__(self):
        self.function_profiler = FunctionProfiler()
        self.memory_profiler = MemoryProfiler()
        self.bottleneck_detector = BottleneckDetector()
        self.profiling_sessions: Dict[str, Dict] = {}
    
    def start_session(self, session_name: str):
        """Start profiling session"""
        self.profiling_sessions[session_name] = {
            'start_time': datetime.now(),
            'end_time': None,
            'duration': 0.0,
            'memory_snapshot': self.memory_profiler.take_snapshot(session_name)
        }
    
    def end_session(self, session_name: str):
        """End profiling session"""
        if session_name in self.profiling_sessions:
            session = self.profiling_sessions[session_name]
            session['end_time'] = datetime.now()
            session['duration'] = (session['end_time'] - session['start_time']).total_seconds()
    
    def get_session_report(self, session_name: str) -> Dict[str, Any]:
        """Get report for profiling session"""
        if session_name not in self.profiling_sessions:
            return {}
        
        session = self.profiling_sessions[session_name]
        
        return {
            'session_name': session_name,
            'start_time': session['start_time'].isoformat(),
            'end_time': session['end_time'].isoformat() if session['end_time'] else None,
            'duration_seconds': round(session['duration'], 3),
            'memory_used_mb': round(session['memory_snapshot']['current_memory'] / 1024 / 1024, 2),
        }
    
    def get_comprehensive_profile(self) -> Dict[str, Any]:
        """Get comprehensive performance profile"""
        return {
            'functions': {
                'slowest': [p.to_dict() for p in self.function_profiler.get_slowest_functions(5)],
                'most_called': [p.to_dict() for p in self.function_profiler.get_most_called_functions(5)],
                'memory_hogs': [p.to_dict() for p in self.function_profiler.get_memory_hogs(5)],
                'statistics': self.function_profiler.get_statistics()
            },
            'memory': self.memory_profiler.get_memory_summary(),
            'bottlenecks': {
                'critical': [b.__dict__ for b in self.bottleneck_detector.get_critical_bottlenecks()],
                'recent': [b.__dict__ for b in self.bottleneck_detector.get_recent_bottlenecks(5)]
            }
        }


# Global instance
performance_profiler = PerformanceProfiler()


@contextmanager
def profile_execution(label: str):
    """Context manager for profiling code block"""
    start_time = time.time()
    tracemalloc.start()
    start_memory = tracemalloc.get_traced_memory()[0]
    
    try:
        yield
    finally:
        end_time = time.time()
        end_memory = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()
        
        duration = end_time - start_time
        memory_delta = end_memory - start_memory
        
        logger.info(f"Profile [{label}]: {duration:.3f}s, {memory_delta / 1024:.1f}KB")


def profile_function(func: Callable) -> Callable:
    """Decorator to profile a function"""
    return performance_profiler.function_profiler.profile_function(func)
