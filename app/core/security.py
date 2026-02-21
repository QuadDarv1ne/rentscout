"""
Модуль безопасности для JWT-аутентификации и управления пользователями.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from enum import Enum
import secrets

from app.core.config import settings


# =============================================================================
# Конфигурация безопасности
# =============================================================================

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 часа
REFRESH_TOKEN_EXPIRE_DAYS = 7


# =============================================================================
# Модели данных
# =============================================================================

class UserRole(str, Enum):
    """Роли пользователей."""
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class TokenData(BaseModel):
    """Данные токена."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: UserRole = UserRole.USER
    exp: Optional[datetime] = None


class TokenPair(BaseModel):
    """Пара токенов (access + refresh)."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserBase(BaseModel):
    """Базовая модель пользователя."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100)
    role: UserRole = UserRole.USER


class UserCreate(UserBase):
    """Модель для создания пользователя."""
    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    """Модель для обновления пользователя."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, min_length=5, max_length=100)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    role: Optional[UserRole] = None


class UserInDB(UserBase):
    """Модель пользователя в БД."""
    id: int
    hashed_password: str
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    is_verified: bool = False


class User(UserInDB):
    """Публичная модель пользователя."""
    hashed_password: str = Field(exclude=True)
    
    model_config = {"from_attributes": True}


# =============================================================================
# Криптография
# =============================================================================

# Контекст для хеширования паролей
pwd_context = CryptContext(
    schemes=["argon2"],  # Argon2 более современный и безопасный
    deprecated="auto",
    argon2__rounds=3,  # Уменьшено для совместимости
    argon2__memory_cost=65536,
    argon2__parallelism=4
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Проверяет соответствие пароля хешу.
    
    Args:
        plain_password: Пароль в открытом виде
        hashed_password: Хеш пароля
        
    Returns:
        True если пароль верный
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Хеширует пароль.
    
    Args:
        password: Пароль в открытом виде
        
    Returns:
        Хеш пароля
    """
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> tuple[bool, list[str]]:
    """
    Проверяет сложность пароля.
    
    Args:
        password: Пароль для проверки
        
    Returns:
        Кортеж (валиден, список проблем)
    """
    problems = []
    
    if len(password) < 8:
        problems.append("Пароль должен быть не менее 8 символов")
    
    if len(password) > 100:
        problems.append("Пароль слишком длинный (максимум 100 символов)")
    
    if not any(c.isupper() for c in password):
        problems.append("Пароль должен содержать заглавные буквы")
    
    if not any(c.islower() for c in password):
        problems.append("Пароль должен содержать строчные буквы")
    
    if not any(c.isdigit() for c in password):
        problems.append("Пароль должен содержать цифры")
    
    if not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?" for c in password):
        problems.append("Пароль должен содержать специальные символы")
    
    # Проверка на распространённые пароли
    common_passwords = [
        "password", "12345678", "qwerty", "admin", "letmein",
        "welcome", "monkey", "dragon", "master", "login"
    ]
    if password.lower() in common_passwords:
        problems.append("Пароль слишком распространённый")
    
    return len(problems) == 0, problems


# =============================================================================
# JWT Token Operations
# =============================================================================

def create_access_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Создаёт access токен.
    
    Args:
        data: Данные для включения в токен
        expires_delta: Время жизни токена
        
    Returns:
        JWT токен
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    })
    
    # Используем дефолтный ключ для тестов если SECRET_KEY не установлен
    secret_key = settings.JWT_SECRET or settings.SECRET_KEY or "test_secret_key_for_development_only_1234567890"
    
    encoded_jwt = jwt.encode(
        to_encode,
        secret_key,
        algorithm=ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Создаёт refresh токен.
    
    Args:
        data: Данные для включения в токен
        expires_delta: Время жизни токена
        
    Returns:
        JWT токен
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    })
    
    # Используем дефолтный ключ для тестов если SECRET_KEY не установлен
    secret_key = settings.JWT_SECRET or settings.SECRET_KEY or "test_secret_key_for_development_only_1234567890"
    
    encoded_jwt = jwt.encode(
        to_encode,
        secret_key,
        algorithm=ALGORITHM
    )
    
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    """
    Декодирует JWT токен.
    
    Args:
        token: JWT токен
        
    Returns:
        TokenData если токен валиден, None иначе
    """
    try:
        # Используем дефолтный ключ для тестов если SECRET_KEY не установлен
        secret_key = settings.JWT_SECRET or settings.SECRET_KEY or "test_secret_key_for_development_only_1234567890"
        
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[ALGORITHM]
        )
        
        user_id: int = payload.get("sub")
        username: str = payload.get("username")
        role_str: str = payload.get("role", UserRole.USER.value)
        token_type: str = payload.get("type", "access")
        
        if user_id is None:
            return None
        
        # Преобразуем строку роли в UserRole enum
        try:
            role = UserRole(role_str)
        except ValueError:
            role = UserRole.USER
        
        return TokenData(
            user_id=user_id,
            username=username,
            role=role,
            token_type=token_type
        )
    
    except (JWTError, Exception):
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """
    Проверяет валидность токена.
    
    Args:
        token: JWT токен
        token_type: Тип токена (access или refresh)
        
    Returns:
        TokenData если токен валиден, None иначе
    """
    token_data = decode_token(token)
    
    if token_data is None:
        return None
    
    if token_data.token_type != token_type:
        return None
    
    return token_data


def create_token_pair(user_id: int, username: str, role: UserRole = UserRole.USER) -> TokenPair:
    """
    Создаёт пару токенов (access + refresh).
    
    Args:
        user_id: ID пользователя
        username: Имя пользователя
        role: Роль пользователя
        
    Returns:
        TokenPair с access и refresh токенами
    """
    token_data = {
        "sub": user_id,
        "username": username,
        "role": role.value
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


def refresh_access_token(refresh_token: str) -> Optional[TokenPair]:
    """
    Обновляет пару токенов используя refresh токен.
    
    Args:
        refresh_token: Refresh токен
        
    Returns:
        Новая пара токенов или None если refresh токен невалиден
    """
    token_data = verify_token(refresh_token, token_type="refresh")
    
    if token_data is None or token_data.user_id is None:
        return None
    
    return create_token_pair(
        user_id=token_data.user_id,
        username=token_data.username or "",
        role=token_data.role
    )


# =============================================================================
# Утилиты безопасности
# =============================================================================

def generate_verification_token() -> str:
    """
    Генерирует токен для верификации email.
    
    Returns:
        Случайный токен (64 символа)
    """
    return secrets.token_urlsafe(64)


def generate_reset_token() -> str:
    """
    Генерирует токен для сброса пароля.
    
    Returns:
        Случайный токен (64 символа)
    """
    return secrets.token_urlsafe(64)


def safe_compare(value1: str, value2: str) -> bool:
    """
    Безопасное сравнение строк (защита от timing attack).
    
    Args:
        value1: Первая строка
        value2: Вторая строка
        
    Returns:
        True если строки равны
    """
    return secrets.compare_digest(value1, value2)


# =============================================================================
# Dependencies для FastAPI
# =============================================================================

async def get_current_user_from_token(token: str) -> TokenData:
    """
    Получает текущего пользователя из токена.
    
    Args:
        token: JWT токен
        
    Returns:
        TokenData текущего пользователя
        
    Raises:
        HTTPException: Если токен невалиден
    """
    from fastapi import HTTPException, status
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = verify_token(token)
    
    if token_data is None:
        raise credentials_exception
    
    return token_data


async def get_current_admin_user(token_data: TokenData) -> TokenData:
    """
    Проверяет что пользователь является администратором.
    
    Args:
        token_data: Данные токена текущего пользователя
        
    Returns:
        TokenData если пользователь админ
        
    Raises:
        HTTPException: Если пользователь не админ
    """
    from fastapi import HTTPException, status
    
    if token_data.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется права администратора"
        )
    
    return token_data


async def get_current_moderator_or_admin(token_data: TokenData) -> TokenData:
    """
    Проверяет что пользователь является модератором или администратором.
    
    Args:
        token_data: Данные токена текущего пользователя
        
    Returns:
        TokenData если пользователь модератор или админ
        
    Raises:
        HTTPException: Если пользователь не модератор/админ
    """
    from fastapi import HTTPException, status
    
    if token_data.role not in [UserRole.MODERATOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется права модератора или администратора"
        )
    
    return token_data


# =============================================================================
# Экспорт
# =============================================================================

__all__ = [
    # Модели
    "UserRole",
    "TokenData",
    "TokenPair",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserInDB",
    "User",
    
    # Пароли
    "verify_password",
    "get_password_hash",
    "validate_password_strength",
    
    # JWT токены
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "verify_token",
    "create_token_pair",
    "refresh_access_token",
    
    # Утилиты
    "generate_verification_token",
    "generate_reset_token",
    "safe_compare",
    
    # Dependencies
    "get_current_user_from_token",
    "get_current_admin_user",
    "get_current_moderator_or_admin",
    
    # Константы
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
]
