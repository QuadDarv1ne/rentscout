"""
CRUD операции для модели User.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.core.security import UserRole, get_password_hash

logger = logging.getLogger(__name__)


# ==================== User CRUD ====================

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Получить пользователя по ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Получить пользователя по имени."""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Получить пользователя по email."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_username_or_email(
    db: AsyncSession, 
    username: str, 
    email: str
) -> Optional[User]:
    """Проверить существует ли пользователь с таким username или email."""
    result = await db.execute(
        select(User).where(
            and_(
                (User.username == username) | (User.email == email)
            )
        )
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
    role: UserRole = UserRole.USER,
    is_verified: bool = False,
) -> User:
    """Создать нового пользователя."""
    hashed_password = get_password_hash(password)
    
    db_user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=role,
        is_verified=is_verified,
        is_active=True,
    )
    
    db.add(db_user)
    await db.flush()
    await db.refresh(db_user)
    
    logger.info(f"Created user: {db_user.id} ({db_user.username})")
    return db_user


async def update_user(
    db: AsyncSession,
    user: User,
    username: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    is_verified: Optional[bool] = None,
) -> User:
    """Обновить данные пользователя."""
    update_data = {}
    
    if username is not None:
        update_data['username'] = username
    if email is not None:
        update_data['email'] = email
    if password is not None:
        update_data['hashed_password'] = get_password_hash(password)
    if role is not None:
        update_data['role'] = role
    if is_active is not None:
        update_data['is_active'] = is_active
    if is_verified is not None:
        update_data['is_verified'] = is_verified
    
    if update_data:
        update_data['updated_at'] = datetime.now(timezone.utc)
        
        stmt = update(User).where(User.id == user.id).values(**update_data)
        await db.execute(stmt)
        await db.flush()
        await db.refresh(user)
    
    return user


async def update_last_login(db: AsyncSession, user: User) -> User:
    """Обновить время последнего входа."""
    stmt = update(User).where(User.id == user.id).values(
        last_login=datetime.now(timezone.utc)
    )
    await db.execute(stmt)
    await db.flush()
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user: User) -> bool:
    """Удалить пользователя."""
    await db.delete(user)
    await db.commit()
    logger.info(f"Deleted user: {user.id} ({user.username})")
    return True


async def list_users(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
) -> List[User]:
    """Получить список пользователей с фильтрацией."""
    query = select(User)
    
    if role is not None:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    query = query.offset(skip).limit(limit).order_by(User.created_at.desc())
    
    result = await db.execute(query)
    return list(result.scalars().all())


async def count_users(
    db: AsyncSession,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
) -> int:
    """Посчитать количество пользователей."""
    from sqlalchemy import func
    
    query = select(func.count(User.id))
    
    if role is not None:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    result = await db.execute(query)
    return result.scalar_one()
