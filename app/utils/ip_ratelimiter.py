"""Rate limiting по IP адресу для API endpoints."""

import time
from typing import Dict, List, Tuple
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from collections import defaultdict
import asyncio

from app.core.config import settings
from app.utils.structured_logger import logger


class IPRateLimiter:
    """Rate limiter на основе IP адреса с поддержкой разных лимитов."""

    def __init__(
        self,
        max_requests: int = 100,
        time_window: int = 60,
        burst_requests: int = 10,
        burst_window: int = 1,
    ):
        """
        Инициализация rate limiter.
        
        Args:
            max_requests: Максимум запросов в основном окне
            time_window: Основное окно в секундах
            burst_requests: Максимум запросов в burst окне
            burst_window: Burst окно в секундах
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.burst_requests = burst_requests
        self.burst_window = burst_window
        
        # Хранилище запросов: {ip: [(timestamp, path), ...]}
        self.requests: Dict[str, List[Tuple[float, str]]] = defaultdict(list)
        
        # Whitelist IP адресов (локальные и доверенные)
        self.whitelist = {"127.0.0.1", "::1", "localhost"}

    def _clean_old_requests(self, ip: str, now: float):
        """Удаление старых запросов вне окна."""
        self.requests[ip] = [
            (req_time, path)
            for req_time, path in self.requests[ip]
            if now - req_time < self.time_window
        ]

    async def check_rate_limit(self, ip: str, path: str) -> Tuple[bool, Dict[str, any]]:
        """
        Проверка rate limit для IP.
        
        Args:
            ip: IP адрес клиента
            path: Путь запроса
            
        Returns:
            (is_allowed, rate_limit_info)
        """
        # Whitelist IP пропускаем
        if ip in self.whitelist:
            return True, {"whitelisted": True}

        now = time.time()

        # Очищаем старые запросы
        self._clean_old_requests(ip, now)

        # Проверяем burst limit (короткое окно)
        recent_requests = [
            req_time
            for req_time, _ in self.requests[ip]
            if now - req_time < self.burst_window
        ]

        if len(recent_requests) >= self.burst_requests:
            oldest_in_burst = min(recent_requests)
            retry_after = int(self.burst_window - (now - oldest_in_burst) + 1)

            return False, {
                "error": "Burst rate limit exceeded",
                "retry_after": retry_after,
                "limit": self.burst_requests,
                "window": self.burst_window,
            }

        # Проверяем основной limit
        if len(self.requests[ip]) >= self.max_requests:
            oldest_request = min(req_time for req_time, _ in self.requests[ip])
            retry_after = int(self.time_window - (now - oldest_request) + 1)

            return False, {
                "error": "Rate limit exceeded",
                "retry_after": retry_after,
                "limit": self.max_requests,
                "window": self.time_window,
            }

        # Записываем запрос
        self.requests[ip].append((now, path))

        # Возвращаем инфо о лимите
        remaining = self.max_requests - len(self.requests[ip])
        reset_time = int(now + self.time_window)

        return True, {
            "limit": self.max_requests,
            "remaining": remaining,
            "reset": reset_time,
        }

    def reset(self, ip: str):
        """Сброс лимита для IP."""
        if ip in self.requests:
            del self.requests[ip]

    def add_to_whitelist(self, ip: str):
        """Добавление IP в whitelist."""
        self.whitelist.add(ip)

    def remove_from_whitelist(self, ip: str):
        """Удаление IP из whitelist."""
        self.whitelist.discard(ip)

    def get_stats(self) -> Dict:
        """Получение статистики rate limiter."""
        now = time.time()
        active_ips = 0
        total_requests_tracked = 0

        for ip, requests in self.requests.items():
            # Учитываем только активные IP (с запросами в последнем окне)
            recent = [r for r in requests if now - r[0] < self.time_window]
            if recent:
                active_ips += 1
                total_requests_tracked += len(recent)

        return {
            "active_ips": active_ips,
            "total_tracked_requests": total_requests_tracked,
            "whitelist_size": len(self.whitelist),
            "config": {
                "max_requests": self.max_requests,
                "time_window": self.time_window,
                "burst_requests": self.burst_requests,
                "burst_window": self.burst_window,
            },
        }


# Глобальный экземпляр IP rate limiter
ip_rate_limiter = IPRateLimiter(
    max_requests=getattr(settings, "API_RATE_LIMIT", 100),
    time_window=60,  # 1 минута
    burst_requests=10,  # 10 запросов
    burst_window=1,  # за 1 секунду
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware для rate limiting по IP."""

    def __init__(
        self,
        app: ASGIApp,
        limiter: IPRateLimiter = ip_rate_limiter,
        exclude_paths: List[str] = None,
    ):
        """
        Инициализация middleware.
        
        Args:
            app: ASGI приложение
            limiter: Rate limiter экземпляр
            exclude_paths: Пути, исключенные из rate limiting
        """
        super().__init__(app)
        self.limiter = limiter
        self.exclude_paths = exclude_paths or ["/api/health", "/docs", "/openapi.json", "/metrics"]

    def _get_client_ip(self, request: Request) -> str:
        """Извлечение IP адреса клиента."""
        # Проверяем заголовки для forwarded IP (если за прокси)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Берем первый IP из списка
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback на client host
        if request.client:
            return request.client.host

        return "unknown"

    async def dispatch(self, request: Request, call_next) -> Response:
        """Обработка запроса с rate limiting."""
        path = request.url.path

        # Пропускаем исключенные пути
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)

        # Получаем IP клиента
        client_ip = self._get_client_ip(request)

        # Проверяем rate limit
        is_allowed, rate_info = await self.limiter.check_rate_limit(client_ip, path)

        if not is_allowed:
            # Логируем превышение лимита
            logger.warning(
                f"Rate limit exceeded for IP {client_ip}",
                extra_data={
                    "ip": client_ip,
                    "path": path,
                    "error": rate_info.get("error"),
                    "retry_after": rate_info.get("retry_after"),
                },
            )

            # Возвращаем 429 Too Many Requests
            raise HTTPException(
                status_code=429,
                detail={
                    "error": rate_info.get("error", "Rate limit exceeded"),
                    "retry_after": rate_info.get("retry_after"),
                    "limit": rate_info.get("limit"),
                },
                headers={
                    "Retry-After": str(rate_info.get("retry_after", 60)),
                    "X-RateLimit-Limit": str(rate_info.get("limit", self.limiter.max_requests)),
                },
            )

        # Обрабатываем запрос
        response = await call_next(request)

        # Добавляем заголовки rate limit в ответ
        if not rate_info.get("whitelisted"):
            response.headers["X-RateLimit-Limit"] = str(rate_info.get("limit", self.limiter.max_requests))
            response.headers["X-RateLimit-Remaining"] = str(rate_info.get("remaining", 0))
            response.headers["X-RateLimit-Reset"] = str(rate_info.get("reset", 0))

        return response
