"""
API эндпоинты для аутентификации и управления пользователями.
"""

from datetime import datetime
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
)
from app.dependencies.auth import (
    get_current_user,
    get_current_admin,
    get_current_moderator_or_admin,
    get_optional_current_user,
    TokenData,
)
from app.utils.logger import logger


router = APIRouter(prefix="/auth", tags=["authentication"])


# =============================================================================
# Mock User Database (для демонстрации)
# =============================================================================
# В production используйте реальную базу данных через repositories

_mock_users_db: dict[int, UserInDB] = {}
_mock_user_id_counter = 1


def get_user_by_username(username: str) -> Optional[UserInDB]:
    """Находит пользователя по имени."""
    for user in _mock_users_db.values():
        if user.username == username:
            return user
    return None


def get_user_by_email(email: str) -> Optional[UserInDB]:
    """Находит пользователя по email."""
    for user in _mock_users_db.values():
        if user.email == email:
            return user
    return None


def create_user_in_db(user_data: UserCreate) -> UserInDB:
    """Создаёт пользователя в БД."""
    global _mock_user_id_counter
    
    user = UserInDB(
        id=_mock_user_id_counter,
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        is_active=True,
        is_verified=False,
    )
    
    _mock_users_db[_mock_user_id_counter] = user
    _mock_user_id_counter += 1
    
    return user


# =============================================================================
# Registration & Login
# =============================================================================

@router.post(
    "/register",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
)
async def register(user_data: UserCreate) -> User:
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
    if get_user_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким именем уже существует"
        )
    
    if get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email уже зарегистрирован"
        )
    
    # Запрет на прямую регистрацию администратором
    if user_data.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя зарегистрироваться администратором напрямую"
        )
    
    # Создание пользователя
    user = create_user_in_db(user_data)
    
    logger.info(f"Пользователь зарегистрирован: {user.username} (ID: {user.id})")
    
    return user


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Вход в систему",
)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenPair:
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
    # Поиск пользователя по username или email
    user = get_user_by_username(form_data.username)
    if not user:
        user = get_user_by_email(form_data.username)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Проверка пароля
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверное имя пользователя или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Проверка активности аккаунта
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт деактивирован"
        )
    
    # Создание токенов
    token_pair = create_token_pair(
        user_id=user.id,
        username=user.username,
        role=user.role
    )
    
    logger.info(f"Пользователь вошёл в систему: {user.username} (ID: {user.id})")
    
    return token_pair


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Обновление токенов",
)
async def refresh_tokens(refresh_token: str) -> TokenPair:
    """
    Обновляет пару токенов используя refresh токен.
    
    ### Использование:
    1. Отправьте refresh_token полученный при логине
    2. Получите новую пару токенов
    3. Старые токены становятся невалидными
    
    ### Когда использовать:
    - Когда access токен истёк
    - Перед истечением access токена (проактивно)
    """
    new_tokens = refresh_access_token(refresh_token)
    
    if not new_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или истёкший refresh токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return new_tokens


@router.post(
    "/logout",
    summary="Выход из системы",
)
async def logout(
    current_user: TokenData = Depends(get_current_user),
    response: Response = None
) -> dict:
    """
    Выход из системы.
    
    ### Важно:
    JWT токены нельзя "отозвать" серверно (они stateless).
    Клиент должен удалить токены локально.
    
    В production используйте blacklist токенов в Redis
    для отзыва токенов до истечения их срока действия.
    """
    logger.info(f"Пользователь вышел из системы: {current_user.username}")
    
    # В production: добавить токен в blacklist
    # await redis.setex(f"blacklist:{token}", ttl, 1)
    
    return {"message": "Выход выполнен успешно"}


# =============================================================================
# User Management
# =============================================================================

@router.get(
    "/me",
    response_model=User,
    summary="Текущий пользователь",
)
async def get_me(current_user: TokenData = Depends(get_current_user)) -> dict:
    """
    Возвращает информацию о текущем пользователе.
    
    ### Используется для:
    - Проверки аутентификации
    - Получения профиля пользователя
    - Проверки роли пользователя
    """
    user = _mock_users_db.get(current_user.user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


@router.put(
    "/me",
    response_model=User,
    summary="Обновление профиля",
)
async def update_me(
    user_data: UserUpdate,
    current_user: TokenData = Depends(get_current_user)
) -> dict:
    """
    Обновляет профиль текущего пользователя.
    
    ### Можно обновить:
    - username (должно быть уникальным)
    - email (должен быть уникальным)
    - password (должен соответствовать требованиям сложности)
    
    ### Нельзя обновить:
    - role (только через администратора)
    """
    user = _mock_users_db.get(current_user.user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Обновление username
    if user_data.username and user_data.username != user.username:
        if get_user_by_username(user_data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким именем уже существует"
            )
        user.username = user_data.username
    
    # Обновление email
    if user_data.email and user_data.email != user.email:
        if get_user_by_email(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email уже зарегистрирован"
            )
        user.email = user_data.email
    
    # Обновление пароля
    if user_data.password:
        is_valid, problems = validate_password_strength(user_data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Слабый пароль", "problems": problems}
            )
        user.hashed_password = get_password_hash(user_data.password)
    
    user.updated_at = datetime.utcnow()
    _mock_users_db[user.id] = user
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


@router.delete(
    "/me",
    summary="Удаление профиля",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_me(
    current_user: TokenData = Depends(get_current_user),
    password: str = None
) -> None:
    """
    Удаляет аккаунт пользователя.
    
    ### Важно:
    - Это действие необратимо
    - Требуется подтверждение паролем
    - Все токены становятся невалидными
    """
    user = _mock_users_db.get(current_user.user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Подтверждение паролем
    if password and not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Неверный пароль"
        )
    
    # Удаление пользователя
    del _mock_users_db[user.id]
    
    logger.info(f"Пользователь удалён: {user.username} (ID: {user.id})")
    
    return None


# =============================================================================
# Admin Endpoints
# =============================================================================

@router.get(
    "/users",
    response_model=List[User],
    summary="Список пользователей (Admin)",
    dependencies=[Depends(get_current_admin)],
)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
) -> List[dict]:
    """
    Возвращает список всех пользователей (только для администраторов).
    
    ### Фильтры:
    - `role`: Фильтр по роли
    - `is_active`: Фильтр по статусу активности
    - `skip`: Пропустить N пользователей
    - `limit`: Максимум N пользователей
    """
    users = list(_mock_users_db.values())
    
    # Применение фильтров
    if role:
        users = [u for u in users if u.role == role]
    
    if is_active is not None:
        users = [u for u in users if u.is_active == is_active]
    
    # Пагинация
    users = users[skip:skip + limit]
    
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "created_at": u.created_at,
            "updated_at": u.updated_at,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
        }
        for u in users
    ]


@router.get(
    "/users/{user_id}",
    response_model=User,
    summary="Пользователь по ID (Admin)",
    dependencies=[Depends(get_current_admin)],
)
async def get_user(user_id: int) -> dict:
    """
    Возвращает информацию о пользователе по ID (только для администраторов).
    """
    user = _mock_users_db.get(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


@router.patch(
    "/users/{user_id}/role",
    response_model=User,
    summary="Изменение роли пользователя (Admin)",
    dependencies=[Depends(get_current_admin)],
)
async def update_user_role(
    user_id: int,
    role: UserRole,
) -> dict:
    """
    Изменяет роль пользователя (только для администраторов).
    
    ### Доступные роли:
    - `user` - обычный пользователь
    - `moderator` - модератор
    - `admin` - администратор
    """
    user = _mock_users_db.get(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    user.role = role
    user.updated_at = datetime.utcnow()
    _mock_users_db[user_id] = user
    
    logger.info(f"Роль пользователя изменена: {user.username} -> {role}")
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


@router.delete(
    "/users/{user_id}",
    summary="Удаление пользователя (Admin)",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_admin)],
)
async def delete_user(user_id: int) -> None:
    """
    Удаляет пользователя (только для администраторов).
    
    ### Важно:
    - Это действие необратимо
    - Нельзя удалить самого себя
    """
    if user_id not in _mock_users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    user = _mock_users_db[user_id]
    logger.info(f"Пользователь удалён администратором: {user.username} (ID: {user.id})")
    
    del _mock_users_db[user_id]
    
    return None


# =============================================================================
# Health Check
# =============================================================================

@router.get(
    "/status",
    summary="Статус аутентификации",
)
async def auth_status(
    user: Optional[TokenData] = Depends(get_optional_current_user)
) -> dict:
    """
    Проверяет статус аутентификации.
    
    ### Возвращает:
    - `authenticated`: True если пользователь аутентифицирован
    - `user_id`: ID пользователя (если аутентифицирован)
    - `role`: Роль пользователя (если аутентифицирован)
    """
    if user:
        return {
            "authenticated": True,
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role.value,
        }
    else:
        return {
            "authenticated": False,
            "role": "anonymous",
        }
