"""
API эндпоинты для аутентификации и управления пользователями.
Использует реальную PostgreSQL базу данных через repositories.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from typing import List, Optional
from pydantic import EmailStr, BaseModel, Field

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
    decode_token,
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
from app.utils.two_factor import two_factor_manager
from app.utils.token_blacklist import token_blacklist
from sqlalchemy.ext.asyncio import AsyncSession
import json
import hashlib

class LoginRequest(BaseModel):
    """Запрос на вход с поддержкой 2FA."""
    username: str
    password: str
    code: Optional[str] = Field(None, description="TOTP код или backup код (если включен 2FA)")


class LoginResponse(BaseModel):
    """Ответ при входе."""
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    requires_2fa: bool = False
    message: str = ""

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
    summary="Вход в систему (OAuth2)",
)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> TokenPair:
    """
    Аутентификация пользователя и получение токенов (OAuth2 Password Flow).

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

    # Проверка 2FA
    if user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется 2FA код. Используйте /api/auth/login-with-2fa",
            headers={"X-2FA-Required": "true"},
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
    "/login-with-2fa",
    response_model=LoginResponse,
    summary="Вход с 2FA",
)
async def login_with_2fa(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    """
    Аутентификация пользователя с поддержкой 2FA.

    ### Flow:
    1. Отправьте username и password
    2. Если включен 2FA, получите ответ с `requires_2fa: true`
    3. Отправьте запрос снова с TOTP кодом

    ### Возвращает:
    - Если требуется 2FA: `{requires_2fa: true, message: "..."}`
    - Если успешно: `{access_token, refresh_token, ...}`
    """
    try:
        # Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        is_allowed, rate_info = await auth_rate_limiter.check_login_attempt(
            client_ip,
            username=login_data.username
        )

        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": rate_info.get("error", "Превышен лимит попыток входа"),
                    "retry_after": rate_info.get("retry_after", 60),
                },
                headers={"Retry-After": str(rate_info.get("retry_after", 60))},
            )

        # Поиск пользователя
        try:
            user = await user_repository.get_user_by_username(db, login_data.username)
            if not user:
                user = await user_repository.get_user_by_email(db, login_data.username)
        except Exception as e:
            logger.error(f"Database error during login: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Сервис временно недоступен",
            )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль",
            )

        # Проверка пароля
        try:
            if not verify_password(login_data.password, user.hashed_password):
                logger.warning(
                    f"Неудачная попытка входа (2FA)",
                    extra_data={
                        "ip": client_ip,
                        "username": login_data.username,
                        "reason": "invalid_password",
                    },
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Неверное имя пользователя или пароль",
                )
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка проверки пароля",
            )

        # Проверка активности
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт заблокирован",
            )

        # Проверка 2FA
        if user.two_factor_enabled:
            if not login_data.code:
                return LoginResponse(
                    requires_2fa=True,
                    message="Требуется 2FA код. Отправьте запрос с полем 'code'"
                )

            # Проверяем TOTP код
            if user.two_factor_secret:
                try:
                    if not two_factor_manager.verify_code(user.two_factor_secret, login_data.code):
                        # Проверяем backup код
                        if user.backup_codes:
                            backup_codes = json.loads(user.backup_codes)
                            used_codes = json.loads(user.backup_codes_used or "[]")

                            is_valid_backup = False
                            for i, code_hash in enumerate(backup_codes):
                                if i not in used_codes:
                                    input_hash = hashlib.sha256(login_data.code.encode()).hexdigest().upper()
                                    if code_hash == input_hash:
                                        is_valid_backup = True
                                        # Отмечаем код как использованный
                                        used_codes.append(i)
                                        await user_repository.update_user_by_id(
                                            db, user.id,
                                            {"backup_codes_used": json.dumps(used_codes)}
                                        )
                                        break

                            if not is_valid_backup:
                                raise HTTPException(
                                    status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail="Неверный 2FA код",
                                )
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Неверный 2FA код",
                            )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"2FA verification error: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Ошибка проверки 2FA кода",
                    )

        # Обновление времени последнего входа
        try:
            await user_repository.update_last_login(db, user)
        except Exception as e:
            logger.warning(f"Failed to update last login: {e}")
            # Не прерываем вход, просто логируем

        # Генерация токенов
        try:
            tokens = create_token_pair(
                user_id=user.id,
                username=user.username,
                role=user.role,
            )
        except Exception as e:
            logger.error(f"Token generation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка генерации токенов",
            )

        logger.info(f"Пользователь вошел с 2FA: {user.username} (ID: {user.id})")

        return LoginResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_type=tokens.token_type,
            expires_in=tokens.expires_in,
            requires_2fa=False,
            message="Вход выполнен успешно"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in login_with_2fa: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера",
        )


class RefreshTokenRequest(BaseModel):
    """Запрос на обновление токена."""
    refresh_token: str = Field(..., description="Refresh токен")


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Обновление токена",
)
async def refresh_token(
    request: Request,
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenPair:
    """
    Обновляет пару токенов используя refresh токен.

    ### Требования:
    - Refresh токен должен быть валидным
    - Пользователь должен быть активен
    - Токен не должен быть отозван

    ### Возвращает:
    - `access_token`: Новый access токен (24 часа)
    - `refresh_token`: Новый refresh токен (7 дней)
    - `token_type`: bearer
    - `expires_in`: Время жизни access токена в секундах
    """
    try:
        # Проверяем refresh токен
        token_data = refresh_access_token(data.refresh_token)

        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный или истёкший refresh токен",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Проверяем blacklist
        is_blacklisted = await token_blacklist.is_blacklisted(data.refresh_token, "refresh")
        if is_blacklisted:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Токен был отозван",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Проверяем существование пользователя
        user = await user_repository.get_user_by_id(db, token_data.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден",
            )

        # Проверяем активность
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Аккаунт заблокирован",
            )

        # Генерируем новую пару токенов
        new_tokens = create_token_pair(
            user_id=user.id,
            username=user.username,
            role=user.role,
        )

        logger.info(f"Токен обновлён для пользователя: {user.username} (ID: {user.id})")

        return new_tokens

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обновления токена",
        )


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


# =============================================================================
# 2FA Login
# =============================================================================

class TwoFactorLoginRequest(BaseModel):
    """Запрос на вход с 2FA."""
    username: str
    password: str
    code: str = Field(..., description="TOTP код или backup код")


@router.post(
    "/login/2fa",
    response_model=TokenPair,
    summary="Вход с 2FA",
)
async def login_2fa(
    request: Request,
    data: TwoFactorLoginRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenPair:
    """
    Аутентификация пользователя с использованием 2FA.
    
    Если у пользователя включен 2FA, обычный /auth/login вернёт ошибку
    с требованием 2FA кода. Используйте этот endpoint для входа с 2FA.
    """
    from app.utils.two_factor import two_factor_manager
    import json
    
    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    is_allowed, rate_info = await auth_rate_limiter.check_login_attempt(
        client_ip,
        username=data.username
    )
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": rate_info.get("error", "Превышен лимит попыток входа"),
                "retry_after": rate_info.get("retry_after", 60),
            },
            headers={"Retry-After": str(rate_info.get("retry_after", 60))},
        )
    
    # Поиск пользователя
    user = await user_repository.get_user_by_username(db, data.username)
    if not user:
        user = await user_repository.get_user_by_email(db, data.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
        )
    
    # Проверка пароля
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
        )
    
    # Проверка активности
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован",
        )
    
    # Проверка что 2FA включен
    if not user.two_factor_enabled or not user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA не включен для этого пользователя"
        )
    
    # Проверяем код
    code_valid = False
    method = ""
    
    # Пробуем TOTP
    if two_factor_manager.verify_code(user.two_factor_secret, data.code):
        code_valid = True
        method = "totp"
    # Пробуем backup код
    elif user.backup_codes:
        backup_codes = json.loads(user.backup_codes)
        is_valid, code_index = two_factor_manager.verify_backup_code(backup_codes, data.code)
        if is_valid:
            code_valid = True
            method = "backup"
            # Отмечаем код как использованный
            used_codes = json.loads(user.backup_codes_used or "[]")
            used_codes.append(code_index)
            await user_repository.update_user_by_id(
                db, user.id, {"backup_codes_used": json.dumps(used_codes)}
            )
    
    if not code_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный код 2FA"
        )
    
    # Обновление времени последнего входа
    await user_repository.update_last_login(db, user)
    
    # Генерация токенов
    tokens = create_token_pair(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )
    
    logger.info(f"Пользователь вошел с 2FA: {user.username} (method: {method})")
    
    return tokens
