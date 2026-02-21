"""
Тесты для модуля аутентификации (auth endpoints).

Проверяют:
- Регистрацию пользователей
- Вход в систему (login)
- Обновление токенов (refresh)
- Выход из системы (logout)
- Получение и обновление профиля
- Удаление профиля
- Админские эндпоинты
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# Тесты регистрации
# =============================================================================

class TestRegistration:
    """Тесты эндпоинта /api/auth/register"""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient):
        """Успешная регистрация нового пользователя"""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "StrongPass123!",
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["role"] == "user"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient):
        """Регистрация со слабым паролем должна быть отклонена"""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "weakuser",
                "email": "weak@example.com",
                "password": "123",  # Слишком короткий
            }
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Слабый пароль" in str(data["detail"])

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client: AsyncClient):
        """Регистрация с существующим именем должна быть отклонена"""
        # Сначала регистрируем первого пользователя
        await client.post(
            "/api/auth/register",
            json={
                "username": "duplicateuser",
                "email": "first@example.com",
                "password": "StrongPass123!",
            }
        )

        # Пытаемся зарегистрировать второго с тем же именем
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "duplicateuser",
                "email": "second@example.com",
                "password": "StrongPass123!",
            }
        )
        assert response.status_code == 400
        assert "Пользователь с таким именем уже существует" in str(response.json()["detail"])

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client: AsyncClient):
        """Регистрация с существующим email должна быть отклонена"""
        # Сначала регистрируем первого пользователя
        await client.post(
            "/api/auth/register",
            json={
                "username": "emailuser1",
                "email": "duplicate@example.com",
                "password": "StrongPass123!",
            }
        )

        # Пытаемся зарегистрировать второго с тем же email
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "emailuser2",
                "email": "duplicate@example.com",
                "password": "StrongPass123!",
            }
        )
        assert response.status_code == 400
        assert "Email уже зарегистрирован" in str(response.json()["detail"])

    @pytest.mark.asyncio
    async def test_register_admin_role_forbidden(self, client: AsyncClient):
        """Регистрация сразу как администратор должна быть запрещена"""
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "adminuser",
                "email": "admin@example.com",
                "password": "StrongPass123!",
                "role": "admin",
            }
        )
        assert response.status_code == 403
        assert "Нельзя зарегистрироваться администратором напрямую" in str(response.json()["detail"])


# =============================================================================
# Тесты входа и токенов
# =============================================================================

class TestLogin:
    """Тесты эндпоинта /api/auth/login"""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient):
        """Успешный вход с получением токенов"""
        # Сначала регистрируем пользователя
        await client.post(
            "/api/auth/register",
            json={
                "username": "loginuser",
                "email": "login@example.com",
                "password": "StrongPass123!",
            }
        )

        # Входим
        response = await client.post(
            "/api/auth/login",
            data={
                "username": "loginuser",
                "password": "StrongPass123!",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient):
        """Вход с неправильным паролем"""
        # Регистрируем пользователя
        await client.post(
            "/api/auth/register",
            json={
                "username": "wrongpassuser",
                "email": "wrong@example.com",
                "password": "StrongPass123!",
            }
        )

        # Пытаемся войти с неправильным паролем
        response = await client.post(
            "/api/auth/login",
            data={
                "username": "wrongpassuser",
                "password": "WrongPassword123!",
            }
        )
        assert response.status_code == 401
        assert "Неверное имя пользователя или пароль" in str(response.json()["detail"])

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Вход с несуществующим пользователем"""
        response = await client.post(
            "/api/auth/login",
            data={
                "username": "nonexistent",
                "password": "SomePassword123!",
            }
        )
        assert response.status_code == 401
        assert "Неверное имя пользователя или пароль" in str(response.json()["detail"])


# =============================================================================
# Тесты профиля пользователя
# =============================================================================

class TestUserProfile:
    """Тесты управления профилем пользователя"""

    @pytest.mark.asyncio
    async def test_get_me_authenticated(self, client: AsyncClient):
        """Получение профиля аутентифицированным пользователем"""
        # Регистрируемся и получаем токены
        register_response = await client.post(
            "/api/auth/register",
            json={
                "username": "profileuser",
                "email": "profile@example.com",
                "password": "StrongPass123!",
            }
        )
        user_id = register_response.json()["id"]

        login_response = await client.post(
            "/api/auth/login",
            data={
                "username": "profileuser",
                "password": "StrongPass123!",
            }
        )
        access_token = login_response.json()["access_token"]

        # Получаем профиль
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "profileuser"
        assert data["email"] == "profile@example.com"

    @pytest.mark.asyncio
    async def test_get_me_unauthenticated(self, client: AsyncClient):
        """Получение профиля без аутентификации"""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_me_username(self, client: AsyncClient):
        """Обновление username в профиле"""
        # Регистрируемся
        await client.post(
            "/api/auth/register",
            json={
                "username": "oldusername",
                "email": "update@example.com",
                "password": "StrongPass123!",
            }
        )

        login_response = await client.post(
            "/api/auth/login",
            data={
                "username": "oldusername",
                "password": "StrongPass123!",
            }
        )
        access_token = login_response.json()["access_token"]

        # Обновляем username
        response = await client.put(
            "/api/auth/me",
            json={"username": "newusername"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newusername"

    @pytest.mark.asyncio
    async def test_update_me_password(self, client: AsyncClient):
        """Обновление пароля в профиле"""
        # Регистрируемся
        await client.post(
            "/api/auth/register",
            json={
                "username": "passwordupdateuser",
                "email": "pwdupdate@example.com",
                "password": "StrongPass123!",
            }
        )

        login_response = await client.post(
            "/api/auth/login",
            data={
                "username": "passwordupdateuser",
                "password": "StrongPass123!",
            }
        )
        access_token = login_response.json()["access_token"]

        # Обновляем пароль
        response = await client.put(
            "/api/auth/me",
            json={"password": "NewStrongPass456!"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200

        # Проверяем вход со старым паролем (должен быть отклонён)
        old_password_response = await client.post(
            "/api/auth/login",
            data={
                "username": "passwordupdateuser",
                "password": "StrongPass123!",
            }
        )
        assert old_password_response.status_code == 401

        # Проверяем вход с новым паролем (должен быть успешен)
        new_password_response = await client.post(
            "/api/auth/login",
            data={
                "username": "passwordupdateuser",
                "password": "NewStrongPass456!",
            }
        )
        assert new_password_response.status_code == 200


# =============================================================================
# Тесты refresh токена
# =============================================================================

class TestRefreshToken:
    """Тесты обновления токенов"""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: AsyncClient):
        """Успешное обновление токенов"""
        # Регистрируемся
        await client.post(
            "/api/auth/register",
            json={
                "username": "refreshuser",
                "email": "refresh@example.com",
                "password": "StrongPass123!",
            }
        )

        # Входим
        login_response = await client.post(
            "/api/auth/login",
            data={
                "username": "refreshuser",
                "password": "StrongPass123!",
            }
        )
        refresh_token = login_response.json()["refresh_token"]

        # Обновляем токены
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        # Новые токены должны отличаться от старых
        assert data["access_token"] != login_response.json()["access_token"]

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client: AsyncClient):
        """Обновление с невалидным refresh токеном"""
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid_token"},
        )
        assert response.status_code == 401
        assert "Неверный или истёкший refresh токен" in str(response.json()["detail"])


# =============================================================================
# Тесты logout
# =============================================================================

class TestLogout:
    """Тесты выхода из системы"""

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient):
        """Успешный выход из системы"""
        # Регистрируемся
        await client.post(
            "/api/auth/register",
            json={
                "username": "logoutuser",
                "email": "logout@example.com",
                "password": "StrongPass123!",
            }
        )

        # Входим
        login_response = await client.post(
            "/api/auth/login",
            data={
                "username": "logoutuser",
                "password": "StrongPass123!",
            }
        )
        access_token = login_response.json()["access_token"]

        # Выходим
        response = await client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "Выход выполнен успешно" in str(data.get("message", ""))


# =============================================================================
# Тесты auth status
# =============================================================================

class TestAuthStatus:
    """Тесты проверки статуса аутентификации"""

    @pytest.mark.asyncio
    async def test_auth_status_authenticated(self, client: AsyncClient):
        """Проверка статуса для аутентифицированного пользователя"""
        # Регистрируемся
        await client.post(
            "/api/auth/register",
            json={
                "username": "statususer",
                "email": "status@example.com",
                "password": "StrongPass123!",
            }
        )

        # Входим
        login_response = await client.post(
            "/api/auth/login",
            data={
                "username": "statususer",
                "password": "StrongPass123!",
            }
        )
        access_token = login_response.json()["access_token"]

        # Проверяем статус
        response = await client.get(
            "/api/auth/status",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["username"] == "statususer"

    @pytest.mark.asyncio
    async def test_auth_status_unauthenticated(self, client: AsyncClient):
        """Проверка статуса для неаутентифицированного пользователя"""
        response = await client.get("/api/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is False
        assert data["role"] == "anonymous"
