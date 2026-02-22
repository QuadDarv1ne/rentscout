"""
Тесты для кастомизированной документации API.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Фикстура тестового клиента."""
    with TestClient(app) as test_client:
        yield test_client


class TestCustomDocs:
    """Тесты кастомизированной документации."""

    def test_custom_docs_page(self, client):
        """Тест страницы кастомизированной документации."""
        response = client.get("/docs-custom")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "RentScout API" in response.text
        assert "Swagger UI" in response.text

    def test_standard_docs(self, client):
        """Тест стандартной Swagger документации."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc(self, client):
        """Тест ReDoc документации."""
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_json(self, client):
        """Тест OpenAPI JSON спецификации."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data
        
        # Проверяем что версия указана
        assert data["info"]["title"] == "RentScout"
        assert "version" in data["info"]

    def test_openapi_tags(self, client):
        """Тест тегов в OpenAPI спецификации."""
        response = client.get("/openapi.json")
        data = response.json()
        
        # Проверяем наличие тегов
        tags = [tag["name"] for tag in data.get("tags", [])]
        assert "authentication" in tags
        assert "properties" in tags
        assert "health" in tags

    def test_api_root_endpoint(self, client):
        """Тест корневого API endpoint."""
        response = client.get("/api")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data

    def test_health_endpoint_in_openapi(self, client):
        """Тест наличия health endpoint в OpenAPI."""
        response = client.get("/openapi.json")
        data = response.json()
        
        # Проверяем что health endpoint есть в спецификации
        paths = data["paths"]
        assert "/api/health" in paths

    def test_properties_endpoint_in_openapi(self, client):
        """Тест наличия properties endpoint в OpenAPI."""
        response = client.get("/openapi.json")
        data = response.json()
        
        paths = data["paths"]
        assert "/api/properties" in paths or "/api/properties/search" in paths


class TestAPIDocumentation:
    """Тесты общей документации API."""

    def test_contact_info(self, client):
        """Тест контактной информации."""
        response = client.get("/openapi.json")
        data = response.json()
        
        contact = data["info"].get("contact", {})
        assert "name" in contact or "email" in contact or "url" in contact

    def test_license_info(self, client):
        """Тест информации о лицензии."""
        response = client.get("/openapi.json")
        data = response.json()
        
        license_info = data["info"].get("license", {})
        assert "name" in license_info
        assert license_info["name"] == "MIT License"

    def test_api_version(self, client):
        """Тест версии API."""
        response = client.get("/openapi.json")
        data = response.json()
        
        version = data["info"]["version"]
        assert version is not None
        assert isinstance(version, str)


class TestCustomDocsContent:
    """Тесты содержимого кастомизированной документации."""

    def test_quick_start_section(self, client):
        """Тест секции быстрого старта."""
        response = client.get("/docs-custom")
        assert response.status_code == 200
        assert "Быстрый старт" in response.text or "quick-start" in response.text

    def test_header_links(self, client):
        """Тест ссылок в заголовке."""
        response = client.get("/docs-custom")
        assert response.status_code == 200
        assert "/docs" in response.text
        assert "/redoc" in response.text
        assert "/openapi.json" in response.text
        assert "/api/health" in response.text

    def test_status_badge(self, client):
        """Тест бейджа статуса."""
        response = client.get("/docs-custom")
        assert response.status_code == 200
        assert "Operational" in response.text or "status-badge" in response.text

    def test_example_endpoints(self, client):
        """Тест примеров endpoint'ов."""
        response = client.get("/docs-custom")
        assert response.status_code == 200
        assert "/api/properties" in response.text
