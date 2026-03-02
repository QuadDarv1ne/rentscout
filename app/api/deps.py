"""
Зависимости (dependencies) для FastAPI endpoints.

Использование:
    from app.api.deps import get_db, get_current_user, CommonDeps

    @app.get("/items")
    async def read_items(deps: CommonDeps = Depends(get_common_deps)):
        ...
"""

from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import AsyncSessionLocal
from app.core.config import settings


# ============================================================================
# Database dependencies
# ============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для получения сессии БД.

    Автоматически commit'ит при успехе и rollback при ошибке.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============================================================================
# Authentication dependencies
# ============================================================================

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    Dependency для получения текущего пользователя из JWT токена.

    Returns:
        dict с информацией о пользователе или None если не аутентифицирован
    """
    if not credentials:
        return None

    token = credentials.credentials

    # TODO: Implement JWT token validation
    # from app.core.security import verify_token
    # user = await verify_token(token)

    # Заглушка для разработки
    if settings.DEBUG and token == "dev_token":
        return {"id": 1, "username": "dev_user", "is_admin": True}

    return None


async def get_current_active_user(
    current_user: Optional[dict] = Depends(get_current_user)
) -> dict:
    """Dependency для получения активного пользователя."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # TODO: Check if user is active
    # if not current_user.get("is_active"):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Inactive user"
    #     )

    return current_user


async def get_current_admin_user(
    current_user: dict = Depends(get_current_active_user)
) -> dict:
    """Dependency для получения администратора."""
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


# ============================================================================
# Common dependencies
# ============================================================================

class CommonDeps:
    """Общие зависимости для endpoints."""

    def __init__(
        self,
        db: AsyncSession,
        current_user: Optional[dict] = None,
        request: Optional[Request] = None,
    ):
        self.db = db
        self.current_user = current_user
        self.request = request
        self.user_id: Optional[int] = current_user.get("id") if current_user else None

    @property
    def is_authenticated(self) -> bool:
        return self.current_user is not None

    @property
    def is_admin(self) -> bool:
        return bool(self.current_user and self.current_user.get("is_admin"))


async def get_common_deps(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user),
    request: Request = None,
) -> CommonDeps:
    """Dependency для получения общих зависимостей."""
    return CommonDeps(
        db=db,
        current_user=current_user,
        request=request,
    )


# ============================================================================
# Pagination dependencies
# ============================================================================

class PaginationParams:
    """Параметры пагинации."""

    def __init__(self, page: int = 1, page_size: int = 20):
        self.page = page
        self.page_size = min(page_size, 100)  # Max 100 items per page
        self.offset = (page - 1) * page_size

    @property
    def limit(self) -> int:
        return self.page_size


async def get_pagination(
    page: int = 1,
    page_size: int = 20,
) -> PaginationParams:
    """Dependency для пагинации."""
    return PaginationParams(page=page, page_size=page_size)


# ============================================================================
# Search dependencies
# ============================================================================

class SearchParams:
    """Параметры поиска."""

    def __init__(
        self,
        q: Optional[str] = None,
        city: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        min_rooms: Optional[int] = None,
        max_rooms: Optional[int] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ):
        self.q = q
        self.city = city
        self.min_price = min_price
        self.max_price = max_price
        self.min_rooms = min_rooms
        self.max_rooms = max_rooms
        self.sort_by = sort_by
        self.sort_order = sort_order

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "q": self.q,
            "city": self.city,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "min_rooms": self.min_rooms,
            "max_rooms": self.max_rooms,
            "sort_by": self.sort_by,
            "sort_order": self.sort_order,
        }


async def get_search_params(
    q: Optional[str] = None,
    city: Optional[str] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    min_rooms: Optional[int] = None,
    max_rooms: Optional[int] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> SearchParams:
    """Dependency для параметров поиска."""
    return SearchParams(
        q=q,
        city=city,
        min_price=min_price,
        max_price=max_price,
        min_rooms=min_rooms,
        max_rooms=max_rooms,
        sort_by=sort_by,
        sort_order=sort_order,
    )


# ============================================================================
# Rate limit dependencies
# ============================================================================

async def get_client_ip(request: Request) -> str:
    """Dependency для получения IP клиента."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ============================================================================
# Export
# ============================================================================

__all__ = [
    # Database
    "get_db",
    # Authentication
    "security",
    "get_current_user",
    "get_current_active_user",
    "get_current_admin_user",
    # Common
    "CommonDeps",
    "get_common_deps",
    # Pagination
    "PaginationParams",
    "get_pagination",
    # Search
    "SearchParams",
    "get_search_params",
    # Rate limit
    "get_client_ip",
]
