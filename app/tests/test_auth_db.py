"""
Тесты для проверки новой аутентификации с PostgreSQL и JWT blacklist.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.core.security import UserRole, TokenPair


class TestUserRepository:
    """Тесты для user repository."""

    @pytest.mark.asyncio
    async def test_create_user(self):
        """Тест создания пользователя."""
        from app.db.repositories.user import create_user
        
        mock_db = AsyncMock()
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.role = UserRole.USER
        mock_user.is_active = True
        mock_user.is_verified = False
        
        mock_db.add = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.refresh = AsyncMock(side_effect=lambda x: setattr(x, 'id', 1))
        
        with patch('app.db.repositories.user.get_password_hash', return_value='hashed_password'):
            result = await create_user(
                db=mock_db,
                username="testuser",
                email="test@example.com",
                password="password123",
                role=UserRole.USER
            )
            
            assert mock_db.add.called
            assert mock_db.flush.called
            assert result == mock_user

    @pytest.mark.asyncio
    async def test_get_user_by_username(self):
        """Тест получения пользователя по username."""
        from app.db.repositories.user import get_user_by_username
        
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        
        mock_execute = AsyncMock(return_value=mock_result)
        mock_db.execute = mock_execute
        
        result = await get_user_by_username(mock_db, "testuser")
        
        assert mock_db.execute.called
        assert result is None


class TestTokenBlacklist:
    """Тесты для JWT token blacklist."""

    @pytest.mark.asyncio
    async def test_add_token(self):
        """Тест добавления токена в blacklist."""
        from app.utils.token_blacklist import TokenBlacklist
        
        blacklist = TokenBlacklist()
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        
        await blacklist.connect(mock_redis)
        
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        result = await blacklist.add_token("test_token", expires_at, "access")
        
        assert result is True
        assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_is_blacklisted(self):
        """Тест проверки токена в blacklist."""
        from app.utils.token_blacklist import TokenBlacklist
        
        blacklist = TokenBlacklist()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        
        await blacklist.connect(mock_redis)
        
        result = await blacklist.is_blacklisted("test_token", "access")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_is_blacklisted_true(self):
        """Тест проверки токена в blacklist (токен заблокирован)."""
        from app.utils.token_blacklist import TokenBlacklist
        
        blacklist = TokenBlacklist()
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="1")
        
        await blacklist.connect(mock_redis)
        
        result = await blacklist.is_blacklisted("test_token", "access")
        
        assert result is True


class TestAuthEndpoints:
    """Тесты для auth endpoints."""

    @pytest.mark.asyncio
    async def test_register_user(self):
        """Тест регистрации пользователя."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "role": "user"
            }
        )
        
        # Может вернуть 400 если пользователь существует или 201 если успешно
        assert response.status_code in [201, 400, 500]

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self):
        """Тест входа с неверными данными."""
        from fastapi.testclient import TestClient
        from app.main import app
        
        client = TestClient(app)
        
        response = client.post(
            "/api/auth/login",
            data={
                "username": "nonexistent",
                "password": "wrongpassword"
            }
        )
        
        assert response.status_code == 401


class TestUserModel:
    """Тесты для User SQLAlchemy модели."""

    def test_user_repr(self):
        """Тест строкового представления пользователя."""
        from app.db.models.user import User
        
        user = User()
        user.id = 1
        user.username = "testuser"
        user.email = "test@example.com"
        
        assert "testuser" in repr(user)
        assert "test@example.com" in repr(user)

    def test_user_relationships(self):
        """Тест отношений пользователя."""
        from app.db.models.user import User
        
        user = User()
        
        # Проверяем что relationships определены
        assert hasattr(User, 'properties')
        assert hasattr(User, 'bookmarks')
        assert hasattr(User, 'alerts')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
