"""
Тесты для JWT-аутентификации и безопасности.
"""

import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.core.security import (
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    UserRole,
    TokenData,
    TokenPair,
    verify_password,
    get_password_hash,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_token,
    create_token_pair,
    refresh_access_token,
    generate_verification_token,
    generate_reset_token,
)
from app.core.config import settings


# =============================================================================
# Тесты паролей
# =============================================================================

class TestPasswordHashing:
    """Тесты хеширования паролей."""

    def test_password_hashing(self):
        """Тест хеширования и проверки пароля."""
        password = "SecureP@ssw0rd!123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed)
    
    def test_password_hashing_different_passwords(self):
        """Разные пароли должны иметь разные хеши."""
        password1 = "Password1!"
        password2 = "Password2!"
        
        hash1 = get_password_hash(password1)
        hash2 = get_password_hash(password2)
        
        assert hash1 != hash2
    
    def test_password_hashing_same_password(self):
        """Одинаковые пароли должны иметь разные хеши (из-за соли)."""
        password = "SamePassword123!"
        
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        
        # Хеши должны быть разными из-за случайной соли
        assert hash1 != hash2
        # Но проверка должна работать для обоих
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)
    
    def test_wrong_password_verification(self):
        """Неверный пароль не должен проходить проверку."""
        password = "CorrectP@ss123"
        hashed = get_password_hash(password)
        
        assert not verify_password("WrongPassword!", hashed)


class TestPasswordValidation:
    """Тесты валидации сложности пароля."""

    def test_strong_password(self):
        """Надёжный пароль должен проходить валидацию."""
        strong_password = "SecureP@ssw0rd!123"
        is_valid, problems = validate_password_strength(strong_password)
        
        assert is_valid is True
        assert len(problems) == 0
    
    def test_short_password(self):
        """Короткий пароль не должен проходить валидацию."""
        short_password = "Sh0rt!"
        is_valid, problems = validate_password_strength(short_password)
        
        assert is_valid is False
        assert any("не менее 8 символов" in p for p in problems)
    
    def test_password_no_uppercase(self):
        """Пароль без заглавных букв не должен проходить валидацию."""
        password = "lowercase123!"
        is_valid, problems = validate_password_strength(password)
        
        assert is_valid is False
        assert any("заглавные буквы" in p for p in problems)
    
    def test_password_no_lowercase(self):
        """Пароль без строчных букв не должен проходить валидацию."""
        password = "UPPERCASE123!"
        is_valid, problems = validate_password_strength(password)
        
        assert is_valid is False
        assert any("строчные буквы" in p for p in problems)
    
    def test_password_no_digits(self):
        """Пароль без цифр не должен проходить валидацию."""
        password = "NoDigitsHere!"
        is_valid, problems = validate_password_strength(password)
        
        assert is_valid is False
        assert any("цифры" in p for p in problems)
    
    def test_password_no_special_chars(self):
        """Пароль без спецсимволов не должен проходить валидацию."""
        password = "NoSpecialChars123"
        is_valid, problems = validate_password_strength(password)
        
        assert is_valid is False
        assert any("специальные символы" in p for p in problems)
    
    def test_common_password(self):
        """Распространённый пароль не должен проходить валидацию."""
        common_passwords = ["password", "12345678", "qwerty", "admin"]
        
        for password in common_passwords:
            is_valid, problems = validate_password_strength(password)
            assert is_valid is False
            assert any("распространённый" in p for p in problems)


# =============================================================================
# Тесты JWT токенов
# =============================================================================

class TestAccessToken:
    """Тесты access токенов."""

    def test_create_access_token(self):
        """Создание access токена."""
        data = {"sub": 1, "username": "testuser", "role": "user"}
        token = create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_decode_access_token(self):
        """Декодирование access токена."""
        data = {"sub": 1, "username": "testuser", "role": "user"}
        token = create_access_token(data)
        decoded = decode_token(token)
        
        assert decoded is not None
        assert decoded.user_id == 1
        assert decoded.username == "testuser"
        assert decoded.role == UserRole.USER
    
    def test_verify_access_token(self):
        """Проверка access токена."""
        data = {"sub": 1, "username": "testuser", "role": "admin"}
        token = create_access_token(data)
        verified = verify_token(token, token_type="access")
        
        assert verified is not None
        assert verified.user_id == 1
        assert verified.role == UserRole.ADMIN
    
    def test_access_token_expiration(self):
        """Истечение срока действия access токена."""
        data = {"sub": 1}
        # Создаём токен с прошлым временем истечения
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        # Токен должен быть невалидным
        verified = verify_token(token, token_type="access")
        assert verified is None
    
    def test_access_token_custom_expiration(self):
        """Access токен с кастомным временем истечения."""
        data = {"sub": 1}
        expires_delta = timedelta(hours=2)
        token = create_access_token(data, expires_delta=expires_delta)
        
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded.exp is not None


class TestRefreshToken:
    """Тесты refresh токенов."""

    def test_create_refresh_token(self):
        """Создание refresh токена."""
        data = {"sub": 1, "username": "testuser"}
        token = create_refresh_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_refresh_token(self):
        """Проверка refresh токена."""
        data = {"sub": 1, "username": "testuser", "role": "user"}
        token = create_refresh_token(data)
        verified = verify_token(token, token_type="refresh")
        
        assert verified is not None
        assert verified.user_id == 1
    
    def test_refresh_token_long_expiration(self):
        """Refresh токен должен иметь длительное время жизни."""
        data = {"sub": 1}
        token = create_refresh_token(data)
        decoded = decode_token(token)
        
        assert decoded is not None
        assert decoded.exp is not None
        
        # Refresh токен должен действовать минимум 6 дней
        now = datetime.now(timezone.utc)
        assert decoded.exp > now + timedelta(days=6)


class TestTokenPair:
    """Тесты пары токенов."""

    def test_create_token_pair(self):
        """Создание пары токенов."""
        token_pair = create_token_pair(
            user_id=1,
            username="testuser",
            role=UserRole.USER
        )
        
        assert isinstance(token_pair, TokenPair)
        assert token_pair.access_token
        assert token_pair.refresh_token
        assert token_pair.token_type == "bearer"
        assert token_pair.expires_in == ACCESS_TOKEN_EXPIRE_MINUTES * 60
    
    def test_refresh_access_token(self):
        """Обновление access токена через refresh токен."""
        # Создаём пару токенов
        original_pair = create_token_pair(
            user_id=1,
            username="testuser",
            role=UserRole.USER
        )
        
        # Обновляем токены
        new_pair = refresh_access_token(original_pair.refresh_token)
        
        assert new_pair is not None
        assert new_pair.access_token != original_pair.access_token
        assert new_pair.refresh_token != original_pair.refresh_token
    
    def test_refresh_with_invalid_token(self):
        """Обновление с невалидным refresh токеном."""
        result = refresh_access_token("invalid_token")
        assert result is None
    
    def test_refresh_with_access_token(self):
        """Попытка использовать access токен как refresh."""
        token_pair = create_token_pair(
            user_id=1,
            username="testuser",
            role=UserRole.USER
        )
        
        # Пытаемся использовать access токен для обновления
        result = refresh_access_token(token_pair.access_token)
        assert result is None


# =============================================================================
# Тесты утилит безопасности
# =============================================================================

class TestSecurityUtilities:
    """Тесты утилит безопасности."""

    def test_generate_verification_token(self):
        """Генерация токена верификации."""
        token = generate_verification_token()
        
        assert isinstance(token, str)
        assert len(token) >= 64
    
    def test_generate_reset_token(self):
        """Генерация токена сброса пароля."""
        token = generate_reset_token()
        
        assert isinstance(token, str)
        assert len(token) >= 64
    
    def test_generate_different_tokens(self):
        """Генерируемые токены должны быть разными."""
        token1 = generate_verification_token()
        token2 = generate_verification_token()
        
        assert token1 != token2


class TestTokenData:
    """Тесты модели TokenData."""

    def test_token_data_creation(self):
        """Создание TokenData."""
        token_data = TokenData(
            user_id=1,
            username="testuser",
            role=UserRole.ADMIN
        )
        
        assert token_data.user_id == 1
        assert token_data.username == "testuser"
        assert token_data.role == UserRole.ADMIN
    
    def test_token_data_default_role(self):
        """Роль по умолчанию должна быть USER."""
        token_data = TokenData(user_id=1)
        assert token_data.role == UserRole.USER


# =============================================================================
# Интеграционные тесты
# =============================================================================

class TestAuthenticationFlow:
    """Интеграционные тесты потока аутентификации."""

    def test_full_authentication_flow(self):
        """Полный поток аутентификации: создание токенов -> проверка -> обновление."""
        # 1. Создаём пару токенов
        token_pair = create_token_pair(
            user_id=42,
            username="integration_test_user",
            role=UserRole.MODERATOR
        )
        
        # 2. Проверяем access токен
        access_data = verify_token(token_pair.access_token, token_type="access")
        assert access_data is not None
        assert access_data.user_id == 42
        assert access_data.username == "integration_test_user"
        assert access_data.role == UserRole.MODERATOR
        
        # 3. Проверяем refresh токен
        refresh_data = verify_token(token_pair.refresh_token, token_type="refresh")
        assert refresh_data is not None
        assert refresh_data.user_id == 42
        
        # 4. Обновляем токены
        new_pair = refresh_access_token(token_pair.refresh_token)
        assert new_pair is not None
        
        # 5. Проверяем новые токены
        new_access_data = verify_token(new_pair.access_token, token_type="access")
        assert new_access_data is not None
        assert new_access_data.user_id == 42
        
        # 6. Старый access токен всё ещё должен работать (до истечения)
        old_access_data = verify_token(token_pair.access_token, token_type="access")
        assert old_access_data is not None


class TestUserRolePermissions:
    """Тесты ролей пользователей."""

    def test_user_roles_enum(self):
        """Тест перечисления ролей."""
        assert UserRole.USER.value == "user"
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.MODERATOR.value == "moderator"
    
    def test_token_with_different_roles(self):
        """Токены с разными ролями."""
        for role in UserRole:
            token_pair = create_token_pair(
                user_id=1,
                username=f"test_{role.value}",
                role=role
            )
            
            token_data = verify_token(token_pair.access_token, token_type="access")
            assert token_data is not None
            assert token_data.role == role
