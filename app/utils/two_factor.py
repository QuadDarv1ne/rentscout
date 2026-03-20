"""
2FA (Two-Factor Authentication) модуль.

Поддерживает:
- TOTP (Time-based One-Time Password) - Google Authenticator, Authy и т.д.
- Backup codes для восстановления доступа
"""

import os
import secrets
import pyotp
import qrcode
import io
import base64
import hashlib
from typing import Optional
from datetime import datetime, timezone

from app.core.config import settings
from app.utils.logger import logger


class TwoFactorManager:
    """
    Менеджер для 2FA аутентификации.
    """
    
    # Количество backup кодов
    BACKUP_CODES_COUNT = 8
    
    # Длина backup кода
    BACKUP_CODE_LENGTH = 8
    
    def __init__(self):
        self.app_name = "RentScout"
    
    def generate_secret(self) -> str:
        """Генерирует секретный ключ для TOTP."""
        return pyotp.random_base32()
    
    def get_totp(self, secret: str) -> pyotp.TOTP:
        """Получает TOTP объект для проверки кодов."""
        return pyotp.TOTP(secret)
    
    def generate_qr_code(self, secret: str, username: str, email: str) -> str:
        """
        Генерирует QR-код для сканирования в приложении-аутентификаторе.
        
        Returns:
            Base64 encoded PNG изображение QR-кода
        """
        totp = self.get_totp(secret)
        provisioning_uri = totp.provisioning_name(
            name=username,
            issuer_name=self.app_name
        )
        
        # Генерируем QR код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Конвертируем в base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode()
    
    def verify_code(self, secret: str, code: str, window: int = 1) -> bool:
        """
        Проверяет TOTP код.
        
        Args:
            secret: Секретный ключ пользователя
            code: Код из приложения-аутентификатора
            window: Окно допустимых временных слотов (для компенсацииclock skew)
            
        Returns:
            True если код валидный
        """
        totp = self.get_totp(secret)
        return totp.verify(code, valid_window=window)
    
    def generate_backup_codes(self) -> list[str]:
        """
        Генерирует список backup кодов.
        
        Returns:
            Список backup кодов (хэшированных для хранения)
        """
        codes = []
        for _ in range(self.BACKUP_CODES_COUNT):
            # Генерируем случайный код
            code = secrets.token_hex(self.BACKUP_CODE_LENGTH // 2).upper()
            # Хэшируем для безопасного хранения
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            codes.append(code_hash)
        
        return codes
    
    def verify_backup_code(self, stored_codes: list[str], code: str) -> tuple[bool, int]:
        """
        Проверяет backup код.
        
        Args:
            stored_codes: Список хэшированных backup кодов
            code: Введённый пользователем код
            
        Returns:
            (валидность, индекс использованного кода)
        """
        code_hash = hashlib.sha256(code.encode()).upper()
        
        for i, stored_hash in enumerate(stored_codes):
            if stored_hash == code_hash:
                return True, i
        
        return False, -1
    
    def generate_setup_data(self, secret: str, username: str, email: str) -> dict:
        """
        Генерирует данные для настройки 2FA.
        
        Returns:
            Dict с secret, qr_code и backup_codes
        """
        backup_codes = self.generate_backup_codes()
        
        return {
            "secret": secret,
            "qr_code": self.generate_qr_code(secret, username, email),
            "backup_codes": backup_codes,  # Возвращаются только при настройке!
        }


# Глобальный экземпляр
two_factor_manager = TwoFactorManager()


async def get_two_factor_manager() -> TwoFactorManager:
    """Dependency для получения 2FA менеджера."""
    return two_factor_manager
