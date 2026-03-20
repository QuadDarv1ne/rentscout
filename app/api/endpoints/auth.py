"""
API эндпоинты для аутентификации и управления пользователями.
Использует реальную PostgreSQL базу данных через repositories.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from typing import List, Optional
from pydantic import EmailStr

from app.core.security import (
    UserCreate,
    UserUpdate,
    User,
    UserInDB,
    TokenPair,
    UserRole,
    verify_password,
    get_password_hash,
    validate_password_strength,
    create_token_pair,
    refresh_access_token,
    generate_verification_token,
    verify_token,
)
from app.dependencies.auth import (
    get_current_user,
    get_current_admin,
    get_current_moderator_or_admin,
    get_optional_current_user,
    TokenData,
    get_token_from_request,
)
from app.utils.logger import logger
from app.utils.auth_ratelimiter import auth_rate_limiter
from app.db.session import get_db
from app.db.repositories import user as user_repository
from app.db.models.user import User as UserDB
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["authentication"])


# =============================================================================
# Вспомогательные функции
# =============================================================================

async def get_user_from_db_or_raise(db: AsyncSession, username: str, email: str):
    """Проверяет существование пользователя по username или email."""
    existing_user = await user_repository.get_user_by_username_or_email(db, username, email)
    if existing_user:
        if existing_user.username == username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким именем уже существует"
            )
        if existing_user.email == email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email уже зарегистрирован"
            )


def convert_db_user_to_pydantic(db_user: UserDB) -> UserInDB:
    """Конвертирует SQLAlchemy модель в Pydantic модель."""
    return UserInDB(
        id=db_user.id,
        username=db_user.username,
        email=db_user.email,
        hashed_password=db_user.hashed_password,
        role=db_user.role,
        created_at=db_user.created_at,
        updated_at=db_user.updated_at,
        is_active=db_user.is_active,
        is_verified=db_user.is_verified,
    )


# =============================================================================
# Registration & Login
# =============================================================================

@router.post(
    "/register",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
async def register(
    request: Request,
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Регистрирует нового пользователя.

    ### Требования к паролю:
    - Минимум 8 символов
    - Хотя бы одна заглавная буква
    - Хотя бы одна строчная буква
    - Хотя бы одна цифра
    - Хотя бы один специальный символ

    ### Роли:
    - `user` - обычный пользователь (по умолчанию)
    - `admin` - администратор (только через приглашение)
    - `moderator` - модератор
    """
    # Rate limiting для регистрации
    client_ip = request.client.host if request.client else "unknown"
    is_allowed, rate_info = await auth_rate_limiter.check_register_attempt(client_ip)

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": rate_info.get("error", "Превышен лимит попыток регистрации"),
                "retry_after": rate_info.get("retry_after", 60),
            },
            headers={"Retry-After": str(rate_info.get("retry_after", 60))},
        )

    # Проверка сложности пароля
    is_valid, problems = validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Слабый пароль",
                "problems": problems
            }
        )

    # Проверка существования пользователя
    await get_user_from_db_or_raise(db, user_data.username, user_data.email)

    # Запрет на прямую регистрацию администратором
    if user_data.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя зарегистрироваться администратором напрямую"
        )

    # Создание пользователя
    user = await user_repository.create_user(
        db=db,
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role,
        is_verified=False,
    )

    logger.info(f"Пользователь зарегистрирован: {user.username} (ID: {user.id})")

    return convert_db_user_to_pydantic(user)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Вход в систему",
)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> TokenPair:
    """
    Аутентификация пользователя и получение токенов.

    ### OAuth2 Password Flow:
    - username: Имя пользователя или email
    - password: Пароль
    - grant_type: password (по умолчанию)
    - scope: (опционально)

    ### Возвращает:
    - `access_token`: JWT токен для доступа к API (24 часа)
    - `refresh_token`: Токен для обновления access токена (7 дней)
    - `token_type`: bearer
    - `expires_in`: Время жизни access токена в секундах
    """
    # Rate limiting для login (защита от brute-force)
    client_ip = request.client.host if request.client else "unknown"
    is_allowed, rate_info = await auth_rate_limiter.check_login_attempt(
        client_ip,
        username=form_data.username
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": rate_info.get("error", "Превышен лимит попыток входа"),
                "retry_after": rate_info.get("retry_after", 60),
                "banned": rate_info.get("banned", False),
            },
            headers={"Retry-After": str(rate_info.get("retry_after", 60))},
        )

    # Поиск пользователя по username или email
    user = await user_repository.get_user_by_username(db, form_data.username)
    if not user:
        user = await user_repository.get_user_by_email(db, form_data.username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Проверка пароля
    if not verify_password(form_data.password, user.hashed_password):
        logger.warning(
            f"Неудачная попытка входа",
            extra_data={
                "ip": client_ip,
                "username": form_data.username,
                "reason": "invalid_password",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Проверка активности аккаунта
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Обновление времени последнего входа
    await user_repository.update_last_login(db, user)

    # Генерация токенов
    tokens = create_token_pair(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    logger.info(f"Пользователь вошел в систему: {user.username} (ID: {user.id})")

    return tokens


@router.post(
    "/logout",
    summary="Выход из системы",
)
async def logout(
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Выход из системы с отзывом токенов.
    
    Добавляет текущий access токен в blacklist.
    """
    from app.utils.token_blacklist import token_blacklist
    from datetime import datetime, timezone, timedelta
    
    # Извлекаем токен из запроса
    token = await get_token_from_request(request)
    
    # Получаем информацию о токене для вычисления TTL
    token_data = verify_token(token)
    if token_data and token_data.exp:
        await token_blacklist.add_token(token, token_data.exp, "access")
    
    logger.info(f"Пользователь вышел из системы: {current_user.username} (ID: {current_user.user_id})")
    
    return {"message": "Выход выполнен успешно", "token_revoked": True}
