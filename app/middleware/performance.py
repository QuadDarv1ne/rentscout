"""Performance monitoring middleware for tracking request metrics."""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.utils.logger import logger
from app.utils.metrics import metrics_collector


class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware to track and log performance metrics for each request."""
    
    def __init__(
        self,
        app: ASGIApp,
        slow_threshold_ms: float = 1000.0,
        log_all_requests: bool = False,
    ):
        """Initialize performance middleware.
        
        Args:
            app: ASGI application
            slow_threshold_ms: Threshold for slow request warnings (ms)
            log_all_requests: Whether to log all requests or only slow ones
        """
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms
        self.log_all_requests = log_all_requests
        self._request_count = 0
        self._total_time = 0.0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and measure performance.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response
        """
        start_time = time.time()
        self._request_count += 1
        
        # Add request start time to state
        request.state.start_time = start_time
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # Track total time
            self._total_time += duration_ms
            
            # Add performance headers
            response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
            response.headers["X-Request-ID"] = getattr(request.state, "request_id", "unknown")
            
            # Log slow requests
            if duration_ms > self.slow_threshold_ms:
                logger.warning(
                    f"Slow request: {request.method} {request.url.path} "
                    f"took {duration_ms:.2f}ms (threshold: {self.slow_threshold_ms}ms)"
                )
            elif self.log_all_requests:
                logger.debug(
                    f"Request: {request.method} {request.url.path} "
                    f"took {duration_ms:.2f}ms"
                )
            
            # Record metrics
            metrics_collector.observe_request_duration(
                duration_ms / 1000,  # Convert to seconds
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code,
            )
            
            return response
        
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"after {duration_ms:.2f}ms - {type(e).__name__}: {e}"
            )
            raise
    
    def get_stats(self) -> dict:
        """Get middleware statistics.
        
        Returns:
            Statistics dictionary
        """
        avg_time = self._total_time / self._request_count if self._request_count > 0 else 0
        
        return {
            "total_requests": self._request_count,
            "total_time_ms": self._total_time,
            "average_time_ms": avg_time,
            "slow_threshold_ms": self.slow_threshold_ms,
        }


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size."""
    
    def __init__(self, app: ASGIApp, max_size_mb: int = 10):
        """Initialize request size limit middleware.
        
        Args:
            app: ASGI application
            max_size_mb: Maximum request body size in MB
        """
        super().__init__(app)
        self.max_size_bytes = max_size_mb * 1024 * 1024
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check request size and process.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response
        """
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        
        if content_length:
            content_length_int = int(content_length)
            if content_length_int > self.max_size_bytes:
                logger.warning(
                    f"Request too large: {content_length_int / 1024 / 1024:.2f}MB "
                    f"(max: {self.max_size_bytes / 1024 / 1024}MB)"
                )
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "Request entity too large",
                        "max_size_mb": self.max_size_bytes / 1024 / 1024,
                    }
                )
        
        return await call_next(request)


class CacheControlMiddleware(BaseHTTPMiddleware):
    """Middleware to add cache control headers."""
    
    def __init__(
        self,
        app: ASGIApp,
        default_ttl: int = 300,
        cache_paths: list = None,
    ):
        """Initialize cache control middleware.
        
        Args:
            app: ASGI application
            default_ttl: Default cache TTL in seconds
            cache_paths: List of paths to cache
        """
        super().__init__(app)
        self.default_ttl = default_ttl
        self.cache_paths = cache_paths or ["/api/properties", "/api/search"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add cache control headers to response.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with cache headers
        """
        response = await call_next(request)
        
        # Check if path should be cached
        should_cache = any(
            request.url.path.startswith(path)
            for path in self.cache_paths
        )
        
        if should_cache and response.status_code == 200:
            response.headers["Cache-Control"] = f"public, max-age={self.default_ttl}"
            response.headers["ETag"] = self._generate_etag(request)
        else:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        
        return response
    
    @staticmethod
    def _generate_etag(request: Request) -> str:
        """Generate ETag for request.
        
        Args:
            request: Request object
            
        Returns:
            ETag string
        """
        import hashlib
        url_str = str(request.url)
        return hashlib.md5(url_str.encode()).hexdigest()


class CompressionMiddleware(BaseHTTPMiddleware):
    """Middleware to compress responses."""
    
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 1000,
        compression_level: int = 6,
    ):
        """Initialize compression middleware.
        
        Args:
            app: ASGI application
            minimum_size: Minimum response size to compress (bytes)
            compression_level: Gzip compression level (1-9)
        """
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Compress response if appropriate.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Possibly compressed response
        """
        response = await call_next(request)
        
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return response
        
        # Check response size
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) < self.minimum_size:
            return response
        
        # Add compression hint header
        response.headers["X-Compression-Available"] = "gzip"
        
        return response
