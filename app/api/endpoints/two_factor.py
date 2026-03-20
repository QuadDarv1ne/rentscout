"""
API эндпоинты для 2FA (Two-Factor Authentication).
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import Optional
import json

from app.dependencies.auth import get_current_user, TokenData
from app.db.session import get_db
from app.db.repositories import user as user_repository
from app.utils.two_factor import two_factor_manager
from app.utils.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/2fa", tags=["2FA"])


# =============================================================================
# Pydantic Models
# =============================================================================

class TwoFactorSetupResponse(BaseModel):
    """Ответ при настройке 2FA."""
    secret: str
    qr_code: str  # Base64 encoded PNG
    backup_codes: list[str]
    message: str


class TwoFactorEnableRequest(BaseModel):
    """Запрос на включение 2FA."""
    code: str = Field(..., description="TOTP код из приложения-аутентификатора")


class TwoFactorDisableRequest(BaseModel):
    """Запрос на отключение 2FA."""
    password: str = Field(..., description="Пароль пользователя")
    code: Optional[str] = Field(None, description="TOTP код (если 2FA включен)")


class TwoFactorLoginRequest(BaseModel):
    """Запрос на вход с 2FA."""
    username: str
    password: str
    code: str = Field(..., description="TOTP код или backup код")


class TwoFactorLoginResponse(BaseModel):
    """Ответ при успешном входе с 2FA."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class BackupCodesResponse(BaseModel):
    """Ответ с backup кодами."""
    backup_codes: list[str]
    message: str


# =============================================================================
# Endpoints
# =============================================================================

@router.post(
    "/setup",
    response_model=TwoFactorSetupResponse,
    summary="Настройка 2FA",
)
async def setup_2fa(
    request: Request,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> TwoFactorSetupResponse:
    """
    Начинает процесс настройки 2FA.
    
    Возвращает секретный ключ, QR-код и backup коды.
    ВНИМАНИЕ: Backup коды отображаются только один раз!
    """
    # Получаем пользователя из БД
    user = await user_repository.get_user_by_id(db, current_user.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Проверяем, что 2FA ещё не включен
    if user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA уже включен"
        )
    
    # Генерируем данные для настройки
    secret = two_factor_manager.generate_secret()
    setup_data = two_factor_manager.generate_setup_data(
        secret=secret,
        username=user.username,
        email=user.email
    )
    
    # Временно сохраняем секрет (не активируем пока не подтвердим)
    # В реальном приложении лучше хранить в Redis с TTL
    await user_repository.update_user(
        db,
        user.id,
        {"two_factor_secret": secret, "backup_codes": json.dumps(setup_data["backup_codes"])}
    )
    
    logger.info(f"Пользователь {user.username} начал настройку 2FA")
    
    return TwoFactorSetupResponse(
        secret=setup_data["secret"],
        qr_code=setup_data["qr_code"],
        backup_codes=setup_data["backup_codes"],
        message="Сохраните backup коды в безопасном месте! Они отображаются только один раз."
    )


@router.post(
    "/enable",
    summary="Подтверждение и включение 2FA",
)
async def enable_2fa(
    request: Request,
    data: TwoFactorEnableRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Подтверждает настройку 2FA и активирует его.
    
    Требует корректный TOTP код для подтверждения.
    """
    user = await user_repository.get_user_by_id(db, current_user.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Проверяем, что есть сохранённый секрет
    if not user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сначала вызовите /2fa/setup"
        )
    
    # Провяем TOTP код
    if not two_factor_manager.verify_code(user.two_factor_secret, data.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный код. Убедитесь, что время на устройстве синхронизировано."
        )
    
    # Активируем 2FA
    await user_repository.update_user(
        db,
        user.id,
        {"two_factor_enabled": True}
    )
    
    logger.info(f"2FA включен для пользователя {user.username}")
    
    return {
        "message": "2FA успешно включен",
        "two_factor_enabled": True
    }


@router.post(
    "/disable",
    summary="Отключение 2FA",
)
async def disable_2fa(
    request: Request,
    data: TwoFactorDisableRequest,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Отключает 2FA.
    
    Требует пароль и (если 2FA включен) TOTP код.
    """
    from app.core.security import verify_password
    
    user = await user_repository.get_user_by_id(db, current_user.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Проверяем пароль
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный пароль"
        )
    
    # Если 2FA включен, проверяем код
    if user.two_factor_enabled:
        if not data.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Требуется TOTP код"
            )
        
        if not two_factor_manager.verify_code(user.two_factor_secret or "", data.code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный TOTP код"
            )
    
    # Отключаем 2FA
    await user_repository.update_user(
        db,
        user.id,
        {
            "two_factor_enabled": False,
            "two_factor_secret": None,
            "backup_codes": None,
            "backup_codes_used": None
        }
    )
    
    logger.info(f"2FA отключен для пользователя {user.username}")
    
    return {
        "message": "2FA успешно отключен",
        "two_factor_enabled": False
    }


@router.post(
    "/verify",
    summary="Проверка кода 2FA",
)
async def verify_2fa(
    request: Request,
    code: str = Field(..., description="TOTP код или backup код"),
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Проверяет код 2FA без создания сессии.
    """
    user = await user_repository.get_user_by_id(db, current_user.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    if not user.two_factor_enabled or not user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="2FA не включен"
        )
    
    # Пробуем TOTP код
    if two_factor_manager.verify_code(user.two_factor_secret, code):
        return {"valid": True, "method": "totp"}
    
    # Пробуем backup код
    if user.backup_codes:
        backup_codes = json.loads(user.backup_codes)
        is_valid, code_index = two_factor_manager.verify_backup_code(backup_codes, code)
        
        if is_valid:
            # Отмечаем backup код как использованный
            used_codes = json.loads(user.backup_codes_used or "[]")
            used_codes.append(code_index)
            
            await user_repository.update_user(
                db,
                user.id,
                {"backup_codes_used": json.dumps(used_codes)}
            )
            
            return {"valid": True, "method": "backup"}
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Неверный код"
    )


@router.get(
    "/status",
    summary="Получить статус 2FA",
)
async def get_2fa_status(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Возвращает статус 2FA для текущего пользователя.
    """
    user = await user_repository.get_user_by_id(db, current_user.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден"
        )
    
    # Подсчитываем оставшиеся backup коды
    backup_codes_remaining = 0
    if user.backup_codes and user.backup_codes_used:
        total_codes = len(json.loads(user.backup_codes))
        used_codes = len(json.loads(user.backup_codes_used))
        backup_codes_remaining = total_codes - used_codes
    
    return {
        "enabled": user.two_factor_enabled,
        "backup_codes_remaining": backup_codes_remaining
    }
