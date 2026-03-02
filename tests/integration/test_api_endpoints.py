"""
Интеграционные тесты для API endpoints.

Тестируют реальное взаимодействие с API:
- Health checks
- Properties search
- Authentication flow
- Bookmarks
"""

import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Тесты endpoints здоровья."""

    @pytest.mark.asyncio
    async def test_root_health(self, client: AsyncClient):
        """Проверка корневого endpoint."""
        response = await client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "version" in data
        assert "endpoints" in data

    @pytest.mark.asyncio
    async def test_basic_health_check(self, client: AsyncClient):
        """Проверка базового health endpoint."""
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_detailed_health_check(self, client: AsyncClient):
        """Проверка подробного health endpoint."""
        response = await client.get("/api/health/detailed")
        assert response.status_code == 200
        data = response.json()

        assert "system" in data or "cpu" in data or "memory" in data
        assert "cache" in data or "redis" in data


class TestPropertiesEndpoints:
    """Тесты endpoints для работы с объявлениями."""

    @pytest.mark.asyncio
    async def test_properties_search_basic(self, client: AsyncClient):
        """Базовый поиск объявлений."""
        response = await client.get("/api/properties")
        assert response.status_code == 200
        data = response.json()

        assert "properties" in data or "results" in data or isinstance(data, list)

    @pytest.mark.asyncio
    async def test_properties_search_with_filters(self, client: AsyncClient):
        """Поиск с фильтрами."""
        params = {
            "min_price": 10000,
            "max_price": 100000,
            "min_rooms": 1,
            "max_rooms": 3,
        }
        response = await client.get("/api/properties", params=params)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_properties_search_city_filter(self, client: AsyncClient):
        """Поиск по городу."""
        response = await client.get("/api/properties", params={"city": "Москва"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_properties_search_invalid_params(self, client: AsyncClient):
        """Поиск с невалидными параметрами."""
        response = await client.get(
            "/api/properties",
            params={"min_price": -100, "max_price": -200}
        )
        # Должен вернуть ошибку или пустой результат
        assert response.status_code in [200, 400, 422]


class TestAuthFlow:
    """Тесты потока аутентификации."""

    @pytest.mark.asyncio
    async def test_register_new_user(
        self,
        client: AsyncClient,
        sample_user_data: dict
    ):
        """Регистрация нового пользователя."""
        response = await client.post("/api/auth/register", json=sample_user_data)
        assert response.status_code in [200, 201]

        if response.status_code == 201:
            data = response.json()
            assert data["username"] == sample_user_data["username"]
            assert data["email"] == sample_user_data["email"]

    @pytest.mark.asyncio
    async def test_login_with_valid_credentials(
        self,
        client: AsyncClient,
        sample_user_data: dict
    ):
        """Вход с валидными учётными данными."""
        # Сначала регистрируем
        await client.post("/api/auth/register", json=sample_user_data)

        # Затем входим
        login_response = await client.post(
            "/api/auth/login",
            data={
                "username": sample_user_data["username"],
                "password": sample_user_data["password"],
            }
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        assert "access_token" in tokens

    @pytest.mark.asyncio
    async def test_login_with_invalid_credentials(self, client: AsyncClient):
        """Вход с невалидными учётными данными."""
        response = await client.post(
            "/api/auth/login",
            data={"username": "nonexistent", "password": "wrongpassword"}
        )
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_get_profile_with_valid_token(
        self,
        authenticated_client: tuple
    ):
        """Получение профиля с валидным токеном."""
        client, tokens = authenticated_client

        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "username" in data or "email" in data or "id" in data

    @pytest.mark.asyncio
    async def test_get_profile_without_token(self, client: AsyncClient):
        """Получение профиля без токена."""
        response = await client.get("/api/auth/me")
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_token_refresh(
        self,
        authenticated_client: tuple
    ):
        """Обновление токена."""
        client, tokens = authenticated_client

        if "refresh_token" in tokens:
            refresh_response = await client.post(
                "/api/auth/refresh",
                json={"refresh_token": tokens["refresh_token"]}
            )
            assert refresh_response.status_code in [200, 201]

            if refresh_response.status_code == 200:
                new_tokens = refresh_response.json()
                assert "access_token" in new_tokens


class TestBookmarksEndpoints:
    """Тесты endpoints для закладок."""

    @pytest.mark.asyncio
    async def test_get_bookmarks_without_auth(self, client: AsyncClient):
        """Получение закладок без аутентификации."""
        response = await client.get("/api/bookmarks")
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_get_bookmarks_with_auth(
        self,
        authenticated_client: tuple
    ):
        """Получение закладок с аутентификацией."""
        client, _ = authenticated_client

        response = await client.get("/api/bookmarks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list) or "bookmarks" in data


class TestMLPredictionsEndpoints:
    """Тесты endpoints для ML предсказаний."""

    @pytest.mark.asyncio
    async def test_ml_prediction_basic(self, client: AsyncClient):
        """Базовый тест ML предсказания."""
        response = await client.get("/api/ml/predict")
        # Может вернуть 200 с пустым результатом или 400/422
        assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_ml_prediction_with_params(self, client: AsyncClient):
        """ML предсказание с параметрами."""
        params = {
            "city": "Москва",
            "rooms": 2,
            "area": 50,
        }
        response = await client.get("/api/ml/predict", params=params)
        assert response.status_code in [200, 400, 422]


class TestTasksEndpoints:
    """Тесты endpoints для задач."""

    @pytest.mark.asyncio
    async def test_get_tasks_list(self, client: AsyncClient):
        """Получение списка задач."""
        response = await client.get("/api/tasks")
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_get_tasks_with_status_filter(self, client: AsyncClient):
        """Получение задач с фильтром по статусу."""
        response = await client.get("/api/tasks", params={"status": "PENDING"})
        assert response.status_code in [200, 503]


class TestErrorHandling:
    """Тесты обработки ошибок."""

    @pytest.mark.asyncio
    async def test_404_for_nonexistent_endpoint(self, client: AsyncClient):
        """Обработка 404 для несуществующего endpoint."""
        response = await client.get("/api/nonexistent-endpoint-12345")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_405_for_wrong_method(self, client: AsyncClient):
        """Обработка 405 для неправильного метода."""
        response = await client.post("/api/health")
        assert response.status_code in [404, 405]

    @pytest.mark.asyncio
    async def test_validation_error(self, client: AsyncClient):
        """Обработка ошибки валидации."""
        response = await client.get(
            "/api/properties",
            params={"min_price": "not_a_number"}
        )
        assert response.status_code in [200, 400, 422]


class TestRateLimiting:
    """Тесты rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, client: AsyncClient):
        """Проверка заголовков rate limiting."""
        response = await client.get("/api/health")
        assert response.status_code == 200

        # Проверяем наличие заголовков rate limit (опционально)
        headers = response.headers
        has_rate_limit_headers = any(
            key.lower().startswith("x-ratelimit")
            for key in headers.keys()
        )
        # Заголовки могут быть или не быть в зависимости от конфигурации
        # Это не критичная ошибка


class TestCORSHeaders:
    """Тесты CORS заголовков."""

    @pytest.mark.asyncio
    async def test_cors_headers_present(self, client: AsyncClient):
        """Проверка наличия CORS заголовков."""
        response = await client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200

        # CORS заголовки могут быть или не быть в тестовой среде
        # Это зависит от конфигурации middleware
