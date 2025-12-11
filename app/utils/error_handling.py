"""
Advanced error handling for parsing operations.

Provides comprehensive error handling with:
- Custom exception hierarchy
- Error recovery strategies
- Error logging and tracking
- Circuit breaker pattern
- Exponential backoff retry logic
- Error analytics
"""

from typing import Any, Dict, List, Optional, Callable, Coroutine, Type, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
import time
from abc import ABC, abstractmethod

from app.utils.logger import logger
from app.utils.advanced_metrics import metrics_reporter


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    LOW = "low"  # Transient, can retry
    MEDIUM = "medium"  # Recoverable with different approach
    HIGH = "high"  # Serious, may need manual intervention
    CRITICAL = "critical"  # System-level failure


class ErrorType(str, Enum):
    """Types of errors that can occur during parsing."""
    NETWORK = "network"  # Connection, timeout issues
    PARSING = "parsing"  # HTML parsing, data extraction
    VALIDATION = "validation"  # Data validation failures
    RATE_LIMIT = "rate_limit"  # Rate limiting
    AUTHENTICATION = "authentication"  # Auth/permission issues
    NOT_FOUND = "not_found"  # Resource not found
    SERVER_ERROR = "server_error"  # Server-side errors
    UNKNOWN = "unknown"  # Unknown error


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================

class RentScoutParsingError(Exception):
    """Base exception for parsing errors."""
    
    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recoverable: bool = True,
        original_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.severity = severity
        self.recoverable = recoverable
        self.original_error = original_error
        self.context = context or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            'message': self.message,
            'type': self.error_type.value,
            'severity': self.severity.value,
            'recoverable': self.recoverable,
            'original_error': str(self.original_error) if self.original_error else None,
            'context': self.context,
            'timestamp': self.timestamp.isoformat(),
        }


class NetworkError(RentScoutParsingError):
    """Network-related errors (connection, timeout)."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=ErrorType.NETWORK,
            severity=ErrorSeverity.LOW,
            recoverable=True,
            **kwargs
        )


class ParsingError(RentScoutParsingError):
    """HTML parsing or data extraction errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=ErrorType.PARSING,
            severity=ErrorSeverity.MEDIUM,
            recoverable=False,
            **kwargs
        )


class ValidationError(RentScoutParsingError):
    """Data validation errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=ErrorType.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            recoverable=True,
            **kwargs
        )


class RateLimitError(RentScoutParsingError):
    """Rate limiting errors."""
    
    def __init__(self, message: str, retry_after: int = 60, **kwargs):
        super().__init__(
            message,
            error_type=ErrorType.RATE_LIMIT,
            severity=ErrorSeverity.LOW,
            recoverable=True,
            **kwargs
        )
        self.retry_after = retry_after


class AuthenticationError(RentScoutParsingError):
    """Authentication/authorization errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            error_type=ErrorType.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            recoverable=False,
            **kwargs
        )


# ============================================================================
# ERROR TRACKING & ANALYTICS
# ============================================================================

@dataclass
class ErrorRecord:
    """Record of an error occurrence."""
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    source: str
    timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'error_type': self.error_type.value,
            'severity': self.severity.value,
            'message': self.message,
            'source': self.source,
            'timestamp': self.timestamp.isoformat(),
            'recoverable': self.recoverable,
            'retry_count': self.retry_count,
        }


class ErrorTracker:
    """Track errors across parsing operations."""
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize error tracker.
        
        Args:
            max_history: Maximum number of errors to keep in history
        """
        self.max_history = max_history
        self.errors: List[ErrorRecord] = []
        self._error_counts: Dict[str, int] = {}
    
    def record_error(
        self,
        error: RentScoutParsingError,
        source: str,
        retry_count: int = 0
    ):
        """
        Record an error.
        
        Args:
            error: The error to record
            source: Source where error occurred
            retry_count: Number of retry attempts
        """
        record = ErrorRecord(
            error_type=error.error_type,
            severity=error.severity,
            message=error.message,
            source=source,
            context=error.context,
            recoverable=error.recoverable,
            retry_count=retry_count
        )
        
        self.errors.append(record)
        
        # Update counts
        key = f"{source}:{error.error_type.value}"
        self._error_counts[key] = self._error_counts.get(key, 0) + 1
        
        # Trim history
        if len(self.errors) > self.max_history:
            self.errors = self.errors[-self.max_history:]
        
        logger.warning(f"Error recorded: {error.message} (source: {source})")
        metrics_reporter.record_parser_failure(source, error.error_type.value, 0)
    
    def get_error_rate(self, source: str) -> float:
        """
        Get error rate for a source.
        
        Args:
            source: Source name
        
        Returns:
            Error rate as percentage
        """
        source_errors = [e for e in self.errors if e.source == source]
        if not source_errors:
            return 0.0
        
        # Count in last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_errors = [e for e in source_errors if e.timestamp > one_hour_ago]
        
        return len(recent_errors) / len(source_errors) * 100 if source_errors else 0.0
    
    def get_top_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most common errors.
        
        Args:
            limit: Number of errors to return
        
        Returns:
            List of error summaries
        """
        error_summary = {}
        for error in self.errors:
            key = f"{error.error_type.value}:{error.message}"
            if key not in error_summary:
                error_summary[key] = {
                    'type': error.error_type.value,
                    'message': error.message,
                    'count': 0,
                    'sources': set(),
                }
            error_summary[key]['count'] += 1
            error_summary[key]['sources'].add(error.source)
        
        # Sort by count
        sorted_errors = sorted(
            error_summary.values(),
            key=lambda x: x['count'],
            reverse=True
        )
        
        # Convert sets to lists
        for error in sorted_errors:
            error['sources'] = list(error['sources'])
        
        return sorted_errors[:limit]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get error tracking summary."""
        if not self.errors:
            return {"message": "No errors recorded"}
        
        critical = sum(1 for e in self.errors if e.severity == ErrorSeverity.CRITICAL)
        high = sum(1 for e in self.errors if e.severity == ErrorSeverity.HIGH)
        medium = sum(1 for e in self.errors if e.severity == ErrorSeverity.MEDIUM)
        low = sum(1 for e in self.errors if e.severity == ErrorSeverity.LOW)
        
        recoverable = sum(1 for e in self.errors if e.recoverable)
        
        return {
            'total_errors': len(self.errors),
            'critical': critical,
            'high': high,
            'medium': medium,
            'low': low,
            'recoverable': recoverable,
            'unrecoverable': len(self.errors) - recoverable,
            'top_errors': self.get_top_errors(5),
        }


# ============================================================================
# CIRCUIT BREAKER
# ============================================================================

class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout_seconds: int = 60  # Time before attempting recovery


class CircuitBreaker:
    """Circuit breaker for handling cascading failures."""
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name
            config: Configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
    
    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *args,
        **kwargs
    ) -> Any:
        """
        Call function with circuit breaker protection.
        
        Args:
            func: Async function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            RuntimeError: If circuit is open
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
            else:
                raise RuntimeError(f"Circuit breaker '{self.name}' is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                logger.info(f"Circuit breaker '{self.name}' closed (recovered)")
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.error(f"Circuit breaker '{self.name}' opened (threshold exceeded)")
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt reset."""
        if not self.last_failure_time:
            return True
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.config.timeout_seconds
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'last_failure': self.last_failure_time.isoformat() if self.last_failure_time else None,
        }


# ============================================================================
# RECOVERY STRATEGIES
# ============================================================================

class RecoveryStrategy(ABC):
    """Base class for error recovery strategies."""
    
    @abstractmethod
    async def recover(
        self,
        error: RentScoutParsingError,
        context: Dict[str, Any]
    ) -> bool:
        """
        Attempt to recover from error.
        
        Args:
            error: The error to recover from
            context: Context information
        
        Returns:
            True if recovery successful, False otherwise
        """
        pass


class RetryStrategy(RecoveryStrategy):
    """Retry with exponential backoff."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0
    ):
        """
        Initialize retry strategy.
        
        Args:
            max_attempts: Maximum retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
    
    async def recover(
        self,
        error: RentScoutParsingError,
        context: Dict[str, Any]
    ) -> bool:
        """
        Implement exponential backoff retry.
        
        Args:
            error: The error to recover from
            context: Context with 'retry_func' key
        
        Returns:
            True if retry successful
        """
        if not error.recoverable:
            return False
        
        retry_func = context.get('retry_func')
        if not retry_func:
            return False
        
        for attempt in range(1, self.max_attempts + 1):
            delay = min(
                self.initial_delay * (2 ** (attempt - 1)),
                self.max_delay
            )
            
            logger.info(f"Retry attempt {attempt}/{self.max_attempts} after {delay}s")
            await asyncio.sleep(delay)
            
            try:
                result = await retry_func()
                logger.info(f"Retry succeeded on attempt {attempt}")
                return True
            except Exception as e:
                logger.warning(f"Retry attempt {attempt} failed: {e}")
        
        return False


class FallbackStrategy(RecoveryStrategy):
    """Use fallback data source."""
    
    async def recover(
        self,
        error: RentScoutParsingError,
        context: Dict[str, Any]
    ) -> bool:
        """
        Attempt to use fallback source.
        
        Args:
            error: The error to recover from
            context: Context with 'fallback_func' key
        
        Returns:
            True if fallback successful
        """
        fallback_func = context.get('fallback_func')
        if not fallback_func:
            return False
        
        try:
            result = await fallback_func()
            logger.info("Fallback source succeeded")
            return True
        except Exception as e:
            logger.warning(f"Fallback strategy failed: {e}")
            return False


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

error_tracker = ErrorTracker()
circuit_breaker = CircuitBreaker("parser_circuit_breaker")
