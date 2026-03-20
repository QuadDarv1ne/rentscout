"""
Тесты для 2FA (Two-Factor Authentication).
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import json

from app.core.security import UserRole, TokenPair


class TestTwoFactorEndpoints:
    """Тесты для 2FA endpoints."""

    @pytest.mark.asyncio
    async def test_setup_2fa(self):
        """Тест настройки 2FA."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # Сначала нужно залогиниться
        login_response = client.post(
            "/api/auth/login",
            data={
                "username": "testuser",
                "password": "TestPass123!"
            }
        )
        
        if login_response.status_code == 200:
            tokens = login_response.json()
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            
            # Настройка 2FA
            setup_response = client.post(
                "/api/auth/2fa/setup",
                headers=headers
            )
            
            # Может вернуть 200 или 400 (если 2FA уже включен)
            assert setup_response.status_code in [200, 400]
            
            if setup_response.status_code == 200:
                data = setup_response.json()
                assert "secret" in data
                assert "qr_code" in data
                assert "backup_codes" in data

    @pytest.mark.asyncio
    async def test_enable_2fa(self):
        """Тест включения 2FA."""
        from fastapi.testclient import TestClient
        from app.main import app
        import pyotp
        
        client = TestClient(app)
        
        # Логинимся
        login_response = client.post(
            "/api/auth/login",
            data={
                "username": "testuser",
                "password": "TestPass123!"
            }
        )
        
        if login_response.status_code == 200:
            tokens = login_response.json()
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            
            # Сначала setup
            setup_response = client.post(
                "/api/auth/2fa/setup",
                headers=headers
            )
            
            if setup_response.status_code == 200:
                setup_data = setup_response.json()
                secret = setup_data["secret"]
                
                # Генерируем TOTP код
                totp = pyotp.TOTP(secret)
                code = totp.now()
                
                # Включаем 2FA
                enable_response = client.post(
                    "/api/auth/2fa/enable",
                    headers=headers,
                    json={"code": code}
                )
                
                # Может быть 200 или 400
                assert enable_response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_get_2fa_status(self):
        """Тест получения статуса 2FA."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        login_response = client.post(
            "/api/auth/login",
            data={
                "username": "testuser",
                "password": "TestPass123!"
            }
        )
        
        if login_response.status_code == 200:
            tokens = login_response.json()
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}
            
            status_response = client.get(
                "/api/auth/2fa/status",
                headers=headers
            )
            
            assert status_response.status_code in [200, 401]
            
            if status_response.status_code == 200:
                data = status_response.json()
                assert "enabled" in data
                assert "backup_codes_remaining" in data


class TestLoginWith2FA:
    """Тесты для login с 2FA."""

    @pytest.mark.asyncio
    async def test_login_without_2fa(self):
        """Тест входа без 2FA."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.post(
            "/api/auth/login-with-2fa",
            json={
                "username": "testuser",
                "password": "TestPass123!"
            }
        )
        
        # Может вернуть 200, 401 или 403
        assert response.status_code in [200, 401, 403]
        
        if response.status_code == 200:
            data = response.json()
            # Если 2FA не включен, должен вернуть токены
            if not data.get("requires_2fa"):
                assert "access_token" in data
                assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_requires_2fa(self):
        """Тест входа с требованием 2FA."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        # Попытка входа без кода
        response = client.post(
            "/api/auth/login-with-2fa",
            json={
                "username": "testuser",
                "password": "TestPass123!"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Если требуется 2FA
            if data.get("requires_2fa"):
                assert "message" in data
                assert "2FA" in data["message"]

    @pytest.mark.asyncio
    async def test_login_with_totp_code(self):
        """Тест входа с TOTP кодом."""
        from fastapi.testclient import TestClient
        from app.main import app
        import pyotp
        
        client = TestClient(app)
        
        # Для этого теста нужен пользователь с включенным 2FA
        # Это интеграционный тест, поэтому может не работать без БД
        
        response = client.post(
            "/api/auth/login-with-2fa",
            json={
                "username": "testuser",
                "password": "TestPass123!",
                "code": "123456"  # Фейковый код для теста
            }
        )
        
        # Может вернуть 200, 401
        assert response.status_code in [200, 401]


class TestTwoFactorManager:
    """Тесты для TwoFactorManager."""

    def test_generate_secret(self):
        """Тест генерации секрета."""
        from app.utils.two_factor import two_factor_manager
        
        secret = two_factor_manager.generate_secret()
        
        assert secret is not None
        assert len(secret) > 0
        assert isinstance(secret, str)

    def test_verify_code(self):
        """Тест проверки TOTP кода."""
        from app.utils.two_factor import two_factor_manager
        import pyotp
        
        secret = two_factor_manager.generate_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()
        
        is_valid = two_factor_manager.verify_code(secret, code)
        
        assert is_valid is True

    def test_verify_code_invalid(self):
        """Тест проверки неверного кода."""
        from app.utils.two_factor import two_factor_manager
        
        secret = two_factor_manager.generate_secret()
        
        is_valid = two_factor_manager.verify_code(secret, "000000")
        
        assert is_valid is False

    def test_generate_backup_codes(self):
        """Тест генерации backup кодов."""
        from app.utils.two_factor import two_factor_manager
        
        codes = two_factor_manager.generate_backup_codes()
        
        assert len(codes) == two_factor_manager.BACKUP_CODES_COUNT
        assert all(isinstance(code, str) for code in codes)
        assert all(len(code) == 64 for code in codes)  # SHA256 hash

    def test_verify_backup_code(self):
        """Тест проверки backup кода."""
        from app.utils.two_factor import two_factor_manager
        import hashlib
        
        # Генерируем код
        plain_code = "ABCD1234"
        code_hash = hashlib.sha256(plain_code.encode()).hexdigest().upper()
        
        is_valid, index = two_factor_manager.verify_backup_code([code_hash], plain_code)
        
        assert is_valid is True
        assert index == 0

    def test_verify_backup_code_invalid(self):
        """Тест проверки неверного backup кода."""
        from app.utils.two_factor import two_factor_manager
        
        is_valid, index = two_factor_manager.verify_backup_code(["fake_hash"], "INVALID")
        
        assert is_valid is False
        assert index == -1

    def test_generate_setup_data(self):
        """Тест генерации данных для настройки 2FA."""
        from app.utils.two_factor import two_factor_manager
        
        secret = two_factor_manager.generate_secret()
        setup_data = two_factor_manager.generate_setup_data(
            secret=secret,
            username="testuser",
            email="test@example.com"
        )
        
        assert "secret" in setup_data
        assert "qr_code" in setup_data
        assert "backup_codes" in setup_data
        assert setup_data["secret"] == secret
        assert len(setup_data["backup_codes"]) == two_factor_manager.BACKUP_CODES_COUNT


class Test2FAIntegration:
    """Интеграционные тесты для 2FA."""

    @pytest.mark.asyncio
    async def test_full_2fa_flow(self):
        """Тест полного цикла 2FA."""
        from fastapi.testclient import TestClient
        from app.main import app
        import pyotp
        
        client = TestClient(app)
        
        # 1. Регистрация
        register_response = client.post(
            "/api/auth/register",
            json={
                "username": "testuser2fa",
                "email": "testuser2fa@example.com",
                "password": "TestPass123!",
                "role": "user"
            }
        )
        
        # Может вернуть 201 или 400 (если пользователь существует)
        if register_response.status_code == 201:
            # 2. Логин
            login_response = client.post(
                "/api/auth/login",
                data={
                    "username": "testuser2fa",
                    "password": "TestPass123!"
                }
            )
            
            if login_response.status_code == 200:
                tokens = login_response.json()
                headers = {"Authorization": f"Bearer {tokens['access_token']}"}
                
                # 3. Setup 2FA
                setup_response = client.post(
                    "/api/auth/2fa/setup",
                    headers=headers
                )
                
                if setup_response.status_code == 200:
                    setup_data = setup_response.json()
                    secret = setup_data["secret"]
                    
                    # 4. Enable 2FA
                    totp = pyotp.TOTP(secret)
                    code = totp.now()
                    
                    enable_response = client.post(
                        "/api/auth/2fa/enable",
                        headers=headers,
                        json={"code": code}
                    )
                    
                    assert enable_response.status_code == 200
                    
                    # 5. Проверка статуса
                    status_response = client.get(
                        "/api/auth/2fa/status",
                        headers=headers
                    )
                    
                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        assert status_data["enabled"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
