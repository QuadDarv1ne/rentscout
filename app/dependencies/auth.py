"""
Зависимости для JWT-аутентификации.
"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from app.core.security import (
    verify_token,
    TokenData,
    UserRole,
    get_current_user_from_token,
    get_current_admin_user,
    get_current_moderator_or_admin,
)
from app.core.config import settings


# =============================================================================
# HTTP Bearer Security
# =============================================================================

security = HTTPBearer(auto_error=False)


# =============================================================================
# Dependencies
# =============================================================================

async def get_token_from_request(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Извлекает JWT токен из запроса.
    
    Поддерживает получение токена из:
    - Authorization header (Bearer <token>)
    - Cookie (access_token)
    
    Args:
        request: FastAPI request объект
        credentials: HTTP Bearer credentials
        
    Returns:
        JWT токен
        
    Raises:
        HTTPException: Если токен не найден
    """
    # Сначала пробуем получить из Authorization header
    if credentials:
        return credentials.credentials
    
    # Затем пробуем получить из cookie
    token = request.cookies.get("access_token")
    if token:
        return token
    
    # Токен не найден
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется аутентификация",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: str = Depends(get_token_from_request)
) -> TokenData:
    """
    Получает текущего аутентифицированного пользователя.
    
    Args:
        token: JWT токен
        
    Returns:
        TokenData текущего пользователя
        
    Raises:
        HTTPException: Если токен невалиден или истёк
    """
    try:
        token_data = verify_token(token)
        
        if token_data is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный или истёкший токен",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return token_data
    
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не удалось проверить учетные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    Получает текущего активного пользователя.
    
    Args:
        current_user: Данные текущего пользователя
        
    Returns:
        TokenData активного пользователя
    """
    # Здесь можно добавить проверку is_active из БД
    # Пока просто возвращаем текущего пользователя
    return current_user


async def get_current_admin(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    Проверяет что текущий пользователь является администратором.
    
    Args:
        current_user: Данные текущего пользователя
        
    Returns:
        TokenData если пользователь админ
        
    Raises:
        HTTPException: Если пользователь не админ
    """
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется права администратора"
        )
    
    return current_user


async def get_current_moderator_or_admin(
    current_user: TokenData = Depends(get_current_user)
) -> TokenData:
    """
    Проверяет что текущий пользователь является модератором или администратором.
    
    Args:
        current_user: Данные текущего пользователя
        
    Returns:
        TokenData если пользователь модератор или админ
        
    Raises:
        HTTPException: Если пользователь не модератор/админ
    """
    if current_user.role not in [UserRole.MODERATOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется права модератора или администратора"
        )
    
    return current_user


# =============================================================================
# Optional Authentication (для эндпоинтов которые работают и с анонимами)
# =============================================================================

async def get_optional_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[TokenData]:
    """
    Получает текущего пользователя если он аутентифицирован.
    
    Возвращает None если пользователь не аутентифицирован.
    Используется для эндпоинтов которые работают как с анонимами, так и с пользователями.
    
    Args:
        request: FastAPI request объект
        credentials: HTTP Bearer credentials
        
    Returns:
        TokenData или None
    """
    try:
        token = await get_token_from_request(request, credentials)
        token_data = verify_token(token)
        return token_data
    except (HTTPException, JWTError):
        return None


# =============================================================================
# Rate Limit Tiers (разные лимиты для разных ролей)
# =============================================================================

def get_rate_limit_tier(user: Optional[TokenData] = Depends(get_optional_current_user)) -> str:
    """
    Определяет tier rate limiting для пользователя.
    
    Args:
        user: Данные текущего пользователя или None
        
    Returns:
        Название tier (anonymous, user, premium, admin)
    """
    if user is None:
        return "anonymous"
    
    if user.role == UserRole.ADMIN:
        return "admin"
    
    if user.role == UserRole.MODERATOR:
        return "premium"
    
    return "user"


# =============================================================================
# Export
# =============================================================================

__all__ = [
    # Dependencies
    "get_token_from_request",
    "get_current_user",
    "get_current_active_user",
    "get_current_admin",
    "get_current_moderator_or_admin",
    "get_optional_current_user",
    "get_rate_limit_tier",
    
    # Security scheme
    "security",
]
