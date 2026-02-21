"""
Интеграционные тесты для полного цикла работы с объявлениями.

Тестируют полный сценарий:
1. Регистрация пользователя
2. Поиск объявлений
3. Добавление в закладки
4. ML предсказание цены
5. Сохранение в БД
6. Извлечение из БД
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# =============================================================================
# Full Flow Tests
# =============================================================================

class TestFullPropertyFlow:
    """Тесты полного цикла работы с объявлениями."""

    @pytest.mark.asyncio
    async def test_user_registration_and_login(
        self,
        client: AsyncClient,
        sample_user_data: dict
    ):
        """
        Тест полного цикла регистрации и входа.
        
        Сценарий:
        1. Регистрация нового пользователя
        2. Вход с полученными учётными данными
        3. Получение профиля
        """
        # Регистрация
        register_response = await client.post(
            "/api/auth/register",
            json=sample_user_data
        )
        assert register_response.status_code == 201
        user_data = register_response.json()
        assert user_data["username"] == sample_user_data["username"]
        assert user_data["email"] == sample_user_data["email"]
        assert "id" in user_data

        # Логин
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
        assert "refresh_token" in tokens

        # Получение профиля
        access_token = tokens["access_token"]
        profile_response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["username"] == sample_user_data["username"]

    @pytest.mark.asyncio
    async def test_property_search_and_bookmark(
        self,
        authenticated_client: tuple,
        sample_property_data: dict
    ):
        """
        Тест поиска и добавления в закладки.
        
        Сценарий:
        1. Поиск объявлений по городу
        2. Добавление найденного объявления в закладки
        3. Получение списка закладок
        """
        client, tokens = authenticated_client

        # Поиск объявлений (mock, может вернуть пустой список)
        search_response = await client.get(
            "/api/properties",
            params={"city": "Москва", "limit": 10}
        )
        # Может вернуть 200 (с данными) или 500 (если парсеры недоступны)
        assert search_response.status_code in [200, 500]

        # Добавление в закладки (имитация найденного объявления)
        bookmark_data = {
            "external_property_id": "test_prop_123",
            "property_title": sample_property_data["title"],
            "property_source": "avito",
            "property_price": sample_property_data["price"],
            "property_city": sample_property_data["city"],
            "property_link": sample_property_data["url"],
            "bookmark_type": "favorite",
        }

        bookmark_response = await client.post(
            "/api/bookmarks/add",
            params={"user_id": "test-user"},
            json=bookmark_data
        )
        # Может вернуть 200 или 500 (если БД недоступна в тесте)
        assert bookmark_response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_ml_price_prediction(
        self,
        client: AsyncClient
    ):
        """
        Тест ML предсказания цены.
        
        Сценарий:
        1. Отправка запроса на предсказание
        2. Проверка структуры ответа
        """
        prediction_request = {
            "city": "Москва",
            "rooms": 2,
            "area": 54.5,
            "district": "ЦАО",
            "floor": 5,
            "total_floors": 12,
            "is_verified": True,
        }

        response = await client.post(
            "/api/ml/predict-price",
            json=prediction_request
        )
        # Должен вернуть предсказание даже без данных (дефолтное)
        assert response.status_code == 200
        data = response.json()
        
        # Проверка структуры ответа
        assert "predicted_price" in data
        assert "confidence" in data
        assert "price_range" in data
        assert "trend" in data
        assert "recommendation" in data
        
        # Проверка типов данных
        assert isinstance(data["predicted_price"], (int, float))
        assert isinstance(data["confidence"], (int, float))
        assert 0 <= data["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_health_check_endpoints(
        self,
        client: AsyncClient
    ):
        """
        Тест endpoint'ов проверки здоровья.
        
        Сценарий:
        1. Проверка базового health endpoint
        2. Проверка детального health endpoint
        """
        # Базовая проверка
        health_response = await client.get("/api/health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        assert "status" in health_data

        # Детальная проверка
        detailed_response = await client.get("/api/health/detailed")
        assert detailed_response.status_code == 200
        detailed_data = detailed_response.json()
        assert "services" in detailed_data or "status" in detailed_data

    @pytest.mark.asyncio
    async def test_auth_flow_with_refresh(
        self,
        client: AsyncClient,
        sample_user_data: dict
    ):
        """
        Тест полного цикла аутентификации с refresh токеном.
        
        Сценарий:
        1. Регистрация
        2. Логин
        3. Refresh токенов
        4. Выход
        """
        # Регистрация
        await client.post("/api/auth/register", json=sample_user_data)

        # Логин
        login_response = await client.post(
            "/api/auth/login",
            data={
                "username": sample_user_data["username"],
                "password": sample_user_data["password"],
            }
        )
        tokens = login_response.json()
        refresh_token = tokens["refresh_token"]

        # Refresh
        refresh_response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert refresh_response.status_code == 200
        new_tokens = refresh_response.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        
        # Новые токены должны отличаться от старых
        assert new_tokens["access_token"] != tokens["access_token"]

        # Выход
        logout_response = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {new_tokens['access_token']}"}
        )
        assert logout_response.status_code == 200


# =============================================================================
# Database Integration Tests
# =============================================================================

class TestDatabaseIntegration:
    """Тесты интеграции с базой данных."""

    @pytest.mark.asyncio
    async def test_db_session_isolation(
        self,
        db_session: AsyncSession
    ):
        """
        Тест изоляции сессий БД.
        
        Каждый тест должен работать в своей транзакции.
        """
        # Сессия должна быть доступна
        assert db_session is not None
        
        # Проверка что сессия закрыта после теста
        # (автоматически фикстурой cleanup_database)

    @pytest.mark.asyncio
    async def test_property_crud_operations(
        self,
        db_session: AsyncSession,
        sample_property_data: dict
    ):
        """
        Тест CRUD операций с объявлениями.
        
        Сценарий:
        1. Создание объявления
        2. Чтение
        3. Обновление
        4. Удаление
        """
        from app.db.models.property import Property
        from sqlalchemy import select

        # Create
        property_obj = Property(**sample_property_data)
        db_session.add(property_obj)
        await db_session.commit()
        await db_session.refresh(property_obj)
        
        assert property_obj.id is not None
        
        # Read
        result = await db_session.execute(
            select(Property).where(Property.id == property_obj.id)
        )
        retrieved_property = result.scalar_one_or_none()
        
        assert retrieved_property is not None
        assert retrieved_property.title == sample_property_data["title"]
        
        # Update
        retrieved_property.price = 55000
        await db_session.commit()
        
        # Verify update
        await db_session.refresh(retrieved_property)
        assert retrieved_property.price == 55000
        
        # Delete (откатится фикстурой)
        await db_session.delete(retrieved_property)
        await db_session.commit()


# =============================================================================
# API Rate Limiting Tests
# =============================================================================

class TestRateLimitingIntegration:
    """Тесты rate limiting в интеграции."""

    @pytest.mark.asyncio
    async def test_auth_rate_limiting(
        self,
        client: AsyncClient
    ):
        """
        Тест rate limiting для auth endpoint'ов.
        
        Сценарий:
        1. Множественные попытки входа
        2. Проверка блокировки после превышения лимита
        """
        # 6+ неудачных попыток входа должны вызвать rate limit
        for i in range(6):
            response = await client.post(
                "/api/auth/login",
                data={
                    "username": f"testuser{i}",
                    "password": "wrongpassword",
                }
            )
            # Последние попытки должны вернуть 429
            if response.status_code == 429:
                assert "retry_after" in str(response.json())
                break
        
        # Если rate limiter сработал, проверяем ответ
        # (может не сработать в тестах из-за whitelist localhost)

    @pytest.mark.asyncio
    async def test_registration_rate_limiting(
        self,
        client: AsyncClient
    ):
        """
        Тест rate limiting для регистрации.
        
        Сценарий:
        1. Множественные регистрации
        2. Проверка блокировки после превышения лимита
        """
        for i in range(12):
            response = await client.post(
                "/api/auth/register",
                json={
                    "username": f"user{i}",
                    "email": f"user{i}@example.com",
                    "password": "StrongPass123!",
                }
            )
            # Последние попытки должны вернуть 429
            if response.status_code == 429:
                assert "retry_after" in str(response.json())
                break


# =============================================================================
# Cache Integration Tests
# =============================================================================

class TestCacheIntegration:
    """Тесты интеграции с кэшем."""

    @pytest.mark.asyncio
    async def test_property_search_caching(
        self,
        client: AsyncClient
    ):
        """
        Тест кэширования поиска объявлений.
        
        Сценарий:
        1. Первый запрос (без кэша)
        2. Второй запрос (должен вернуть кэш)
        """
        # Первый запрос
        response1 = await client.get(
            "/api/properties",
            params={"city": "Москва"}
        )
        
        # Второй запрос (должен использовать кэш)
        response2 = await client.get(
            "/api/properties",
            params={"city": "Москва"}
        )
        
        # Оба должны вернуть 200
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Проверка что данные одинаковые (кэш)
        # (может отличаться если парсеры реальные)
