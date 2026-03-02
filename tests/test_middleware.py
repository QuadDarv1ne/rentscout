"""Тесты для middleware."""

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

from app.middleware.security import (
    HTTPSRedirectMiddleware,
    SecurityHeadersMiddleware,
    CORSMiddlewareConfig,
)
from app.middleware.compression import GZipMiddleware
from app.core.config import settings


@pytest.fixture
def test_app():
    """Создаёт тестовое приложение с middleware."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    @app.get("/large")
    async def large_endpoint():
        return {"data": "x" * 1000}

    @app.get("/auth/test")
    async def auth_endpoint():
        return {"token": "test"}

    return app


class TestHTTPSRedirectMiddleware:
    """Тесты для HTTPSRedirectMiddleware."""

    def test_redirect_disabled_by_default(self, test_app):
        """Middleware не перенаправляет, когда HTTPS_ENABLED=False."""
        test_app.add_middleware(HTTPSRedirectMiddleware)
        client = TestClient(test_app)

        response = client.get("/test", headers={"host": "example.com"})
        assert response.status_code == 200
        assert response.json() == {"message": "test"}

    def test_no_redirect_for_localhost(self, test_app):
        """Нет редиректа для localhost."""
        test_app.add_middleware(HTTPSRedirectMiddleware)
        client = TestClient(test_app)

        response = client.get(
            "/test",
            headers={"host": "localhost:8000"},
            allow_redirects=False
        )
        assert response.status_code == 200

    def test_no_redirect_for_127_0_0_1(self, test_app):
        """Нет редиректа для 127.0.0.1."""
        test_app.add_middleware(HTTPSRedirectMiddleware)
        client = TestClient(test_app)

        response = client.get(
            "/test",
            headers={"host": "127.0.0.1:8000"},
            allow_redirects=False
        )
        assert response.status_code == 200

    def test_redirect_with_https_enabled(self, monkeypatch, test_app):
        """Редирект работает при включённом HTTPS."""
        monkeypatch.setattr(settings, "HTTPS_ENABLED", True)

        test_app.add_middleware(HTTPSRedirectMiddleware)
        client = TestClient(test_app)

        response = client.get(
            "/test",
            headers={
                "host": "example.com",
                "x-forwarded-proto": "http"
            },
            allow_redirects=False
        )
        assert response.status_code == 301
        assert "https://example.com/test" in response.headers.get("location", "")


class TestSecurityHeadersMiddleware:
    """Тесты для SecurityHeadersMiddleware."""

    def test_security_headers_added(self, test_app):
        """Security headers добавляются к ответу."""
        test_app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(test_app)

        response = client.get("/test")

        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("x-xss-protection") == "1; mode=block"
        assert "default-src 'self'" in response.headers.get("content-security-policy", "")
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "geolocation=()" in response.headers.get("permissions-policy", "")

    def test_hsts_header_when_enabled(self, test_app, monkeypatch):
        """HSTS header добавляется при включённой настройке."""
        monkeypatch.setattr(settings, "HSTS_ENABLED", True)
        monkeypatch.setattr(settings, "HTTPS_ENABLED", True)

        test_app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(test_app)

        response = client.get("/test")
        assert "max-age=31536000" in response.headers.get(
            "strict-transport-security", ""
        )

    def test_cache_headers_for_auth_endpoints(self, test_app):
        """Cache-Control headers для auth endpoints."""
        test_app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(test_app)

        response = client.get("/auth/test")

        assert response.headers.get("cache-control") == (
            "no-store, no-cache, must-revalidate, proxy-revalidate"
        )
        assert response.headers.get("pragma") == "no-cache"
        assert response.headers.get("expires") == "0"


class TestCORSMiddlewareConfig:
    """Тесты для конфигурации CORS."""

    def test_allowed_origins_in_debug_mode(self, monkeypatch):
        """В debug режиме разрешены localhost origins."""
        monkeypatch.setattr(settings, "DEBUG", True)

        origins = CORSMiddlewareConfig.get_allowed_origins()

        assert "http://localhost:3000" in origins
        assert "http://localhost:8000" in origins
        assert "http://127.0.0.1:3000" in origins

    def test_allowed_origins_in_production(self, monkeypatch):
        """В production используются настройки из env."""
        monkeypatch.setattr(settings, "DEBUG", False)
        monkeypatch.setattr(
            settings,
            "ALLOWED_ORIGINS",
            "https://example.com,https://api.example.com"
        )

        origins = CORSMiddlewareConfig.get_allowed_origins()

        assert "https://example.com" in origins
        assert "https://api.example.com" in origins
        assert "http://localhost:3000" not in origins

    def test_cors_config_structure(self):
        """CORS config имеет правильную структуру."""
        config = CORSMiddlewareConfig.get_cors_config()

        assert "allow_origins" in config
        assert "allow_credentials" in config
        assert "allow_methods" in config
        assert "allow_headers" in config
        assert "expose_headers" in config
        assert "max_age" in config
        assert config["max_age"] == 600


class TestGZipMiddleware:
    """Тесты для GZipMiddleware."""

    def test_no_compression_without_accept_encoding(self, test_app):
        """Нет сжатия без Accept-Encoding: gzip."""
        test_app.add_middleware(GZipMiddleware)
        client = TestClient(test_app)

        response = client.get("/large", headers={"accept-encoding": ""})

        assert response.headers.get("content-encoding") != "gzip"

    def test_compression_with_gzip_support(self, test_app):
        """Сжатие работает при поддержке gzip клиентом."""
        test_app.add_middleware(GZipMiddleware, minimum_size=100)
        client = TestClient(test_app)

        response = client.get("/large", headers={"accept-encoding": "gzip"})

        assert response.headers.get("content-encoding") == "gzip"
        assert "vary" in response.headers
        assert "Accept-Encoding" in response.headers.get("vary", "")

    def test_no_compression_for_small_responses(self, test_app):
        """Нет сжатия для маленьких ответов."""
        test_app.add_middleware(GZipMiddleware, minimum_size=500)
        client = TestClient(test_app)

        response = client.get("/test", headers={"accept-encoding": "gzip"})

        assert response.headers.get("content-encoding") != "gzip"

    def test_compression_level(self, test_app):
        """Уровень сжатия применяется корректно."""
        import gzip

        test_app.add_middleware(GZipMiddleware, minimum_size=100, compression_level=9)
        client = TestClient(test_app)

        response = client.get("/large", headers={"accept-encoding": "gzip"})

        # Проверяем, что тело действительно сжато
        assert response.headers.get("content-encoding") == "gzip"
        decompressed = gzip.decompress(response.content)
        assert len(decompressed) > len(response.content)
