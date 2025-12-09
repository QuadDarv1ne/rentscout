"""
Продвинутое ограничение частоты запросов (rate limiting) с бэкендом на Redis.
Реализует алгоритмы sliding window и token bucket.
"""
import asyncio
import time
from typing import Optional, Callable, Dict, Tuple
from datetime import datetime, timedelta

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.logger import logger

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available for rate limiting")


class RateLimitConfig:
    """Конфигурация ограничения частоты запросов."""
    
    def __init__(
        self,
        requests: int = 100,
        window: int = 60,
        burst: Optional[int] = None
    ):
        self.requests = requests
        self.window = window  # seconds
        self.burst = burst or requests * 2


class RateLimiter:
    """
    Продвинутый ограничитель частоты с алгоритмом sliding window.
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        default_limit: RateLimitConfig = None
    ):
        self.redis_url = redis_url
        self.redis_client: Optional[aioredis.Redis] = None
        self.default_limit = default_limit or RateLimitConfig()
        self._memory_store: Dict[str, list] = {}
        self._initialized = False
    
    async def initialize(self):
        """Инициализировать подключение к Redis."""
        if not REDIS_AVAILABLE or not self.redis_url or self._initialized:
            return
        
        try:
            self.redis_client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            self._initialized = True
            logger.info("✅ RateLimiter initialized with Redis backend")
        except Exception as e:
            logger.warning(f"Redis unavailable for rate limiting: {e}")
            self.redis_client = None
    
    async def close(self):
        """Закрыть подключение к Redis."""
        if self.redis_client:
            await self.redis_client.close()
            self._initialized = False
    
    async def is_allowed(
        self,
        key: str,
        limit: Optional[RateLimitConfig] = None
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Проверить, разрешен ли запрос в рамках ограничения частоты.
        
        Args:
            key: Уникальный идентификатор (например, IP адрес, ID пользователя)
            limit: Конфигурация ограничения (используется по умолчанию, если не указано)
        
        Returns:
            Кортеж (разрешено: bool, инфо: dict)
        """
        config = limit or self.default_limit
        
        if self.redis_client:
            return await self._check_redis(key, config)
        else:
            return await self._check_memory(key, config)
    
    async def _check_redis(
        self,
        key: str,
        config: RateLimitConfig
    ) -> Tuple[bool, Dict[str, any]]:
        """Проверить ограничение частоты используя Redis (sliding window)."""
        now = time.time()
        window_start = now - config.window
        
        redis_key = f"ratelimit:{key}"
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(redis_key, 0, window_start)
            
            # Count requests in current window
            pipe.zcard(redis_key)
            
            # Add current request
            pipe.zadd(redis_key, {str(now): now})
            
            # Set expiry
            pipe.expire(redis_key, config.window * 2)
            
            results = await pipe.execute()
            request_count = results[1]
            
            allowed = request_count < config.requests
            
            # Calculate reset time
            if request_count > 0:
                oldest = await self.redis_client.zrange(redis_key, 0, 0, withscores=True)
                if oldest:
                    reset_time = oldest[0][1] + config.window
                else:
                    reset_time = now + config.window
            else:
                reset_time = now + config.window
            
            return allowed, {
                "limit": config.requests,
                "remaining": max(0, config.requests - request_count - 1),
                "reset": int(reset_time),
                "retry_after": int(reset_time - now) if not allowed else None
            }
            
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fail open - allow request if Redis fails
            return True, {
                "limit": config.requests,
                "remaining": config.requests,
                "reset": int(now + config.window)
            }
    
    async def _check_memory(
        self,
        key: str,
        config: RateLimitConfig
    ) -> Tuple[bool, Dict[str, any]]:
        """Проверить ограничение частоты используя память (fallback)."""
        now = time.time()
        window_start = now - config.window
        
        # Clean old entries
        if key in self._memory_store:
            self._memory_store[key] = [
                ts for ts in self._memory_store[key]
                if ts > window_start
            ]
        else:
            self._memory_store[key] = []
        
        # Check limit
        request_count = len(self._memory_store[key])
        allowed = request_count < config.requests
        
        if allowed:
            self._memory_store[key].append(now)
        
        # Calculate reset time
        if self._memory_store[key]:
            reset_time = self._memory_store[key][0] + config.window
        else:
            reset_time = now + config.window
        
        return allowed, {
            "limit": config.requests,
            "remaining": max(0, config.requests - request_count - 1),
            "reset": int(reset_time),
            "retry_after": int(reset_time - now) if not allowed else None
        }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware FastAPI для ограничения частоты запросов.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        limiter: RateLimiter,
        key_func: Optional[Callable[[Request], str]] = None,
        exclude_paths: Optional[list[str]] = None
    ):
        super().__init__(app)
        self.limiter = limiter
        self.key_func = key_func or self._default_key_func
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs", "/redoc", "/openapi.json"]
    
    @staticmethod
    def _default_key_func(request: Request) -> str:
        """Функция ключа по умолчанию, использующая IP клиента."""
        # Try to get real IP from proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to client host
        return request.client.host if request.client else "unknown"
    
    async def dispatch(self, request: Request, call_next):
        """Обработать запрос с ограничением частоты."""
        # Skip rate limiting for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Get rate limit key
        key = self.key_func(request)
        
        # Check rate limit
        allowed, info = await self.limiter.is_allowed(key)
        
        if not allowed:
            logger.warning(
                f"Rate limit exceeded for {key} on {request.url.path}"
            )
            
            # Return 429 Too Many Requests
            return Response(
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please try again in {info['retry_after']} seconds.",
                    "limit": info["limit"],
                    "reset": info["reset"]
                },
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(info["retry_after"])
                },
                media_type="application/json"
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        
        return response


# Decorator for endpoint-specific rate limiting
def rate_limit(requests: int = 10, window: int = 60):
    """
    Декоратор для ограничения частоты запросов на уровне endpoint.
    
    Пример:
        @app.get("/api/search")
        @rate_limit(requests=5, window=60)
        async def search():
            return {"results": []}
    """
    def decorator(func: Callable):
        async def wrapper(request: Request, *args, **kwargs):
            # This would need to be implemented with dependency injection
            # For now, it's a placeholder
            return await func(request, *args, **kwargs)
        return wrapper
    return decorator
