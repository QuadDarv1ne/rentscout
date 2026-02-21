"""
Middleware для HTTPS redirects и security headers.
"""

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Awaitable

from app.core.config import settings
from app.utils.logger import logger


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    Middleware для перенаправления HTTP на HTTPS.
    
    Включается только когда:
    - HTTPS_ENABLED = True
    - Запрос не localhost/127.0.0.1
    - Запрос уже не HTTPS
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Пропускаем localhost в development режиме
        host = request.headers.get("host", "")
        is_localhost = host.startswith("localhost") or host.startswith("127.0.0.1")
        
        # Проверяем схему
        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        is_https = scheme == "https"
        
        # Если HTTPS не включён или это localhost или уже HTTPS - пропускаем
        if not settings.HTTPS_ENABLED or is_localhost or is_https:
            return await call_next(request)
        
        # Перенаправляем на HTTPS
        https_url = str(request.url).replace("http://", "https://", 1)
        logger.info(f"Redirecting HTTP to HTTPS: {https_url}")
        
        return RedirectResponse(
            url=https_url,
            status_code=301,  # Permanent redirect
            headers=request.headers
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware для добавления security headers.
    
    Добавляет заголовки:
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Content-Security-Policy
    - Referrer-Policy
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        
        # HSTS (только для HTTPS или когда включён)
        if settings.HSTS_ENABLED and (settings.HTTPS_ENABLED or request.url.scheme == "https"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # Запрет MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Защита от clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # XSS protection (для старых браузеров)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdn.jsdelivr.net; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none';"
        )
        
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions Policy (бывший Feature-Policy)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )
        
        # Cache-Control для чувствительных данных
        if request.url.path.startswith("/api/auth"):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, proxy-revalidate"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        
        return response


class CORSMiddlewareConfig:
    """
    Конфигурация CORS с безопасными настройками по умолчанию.
    
    В production следует указывать конкретные origins.
    """
    
    @staticmethod
    def get_allowed_origins() -> list[str]:
        """
        Возвращает список разрешённых origins.
        
        В development: localhost
        В production: из настроек
        """
        if settings.DEBUG:
            return [
                "http://localhost:3000",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
            ]
        
        # В production используем настройки из env
        if hasattr(settings, 'ALLOWED_ORIGINS') and settings.ALLOWED_ORIGINS:
            return [
                origin.strip() 
                for origin in settings.ALLOWED_ORIGINS.split(',')
            ]
        
        # Default empty - нужно настроить в production
        return []
    
    @staticmethod
    def get_cors_config() -> dict:
        """
        Возвращает конфигурацию для FastAPI CORS middleware.
        """
        return {
            "allow_origins": CORSMiddlewareConfig.get_allowed_origins(),
            "allow_credentials": getattr(settings, 'CORS_ALLOW_CREDENTIALS', True),
            "allow_methods": ["*"],
            "allow_headers": ["*"],
            "expose_headers": [
                "X-Request-ID",
                "X-Correlation-ID",
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "X-RateLimit-Reset",
            ],
            "max_age": 600,  # 10 минут
        }


__all__ = [
    "HTTPSRedirectMiddleware",
    "SecurityHeadersMiddleware",
    "CORSMiddlewareConfig",
]
