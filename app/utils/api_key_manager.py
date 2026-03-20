"""
API Key Security.

Безопасное хранение и проверка API ключей:
- Хеширование ключей (SHA256)
- Ротация ключей
- Проверка срока действия
- Ограничение по IP
"""

import hashlib
import secrets
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json


@dataclass
class APIKey:
    """Модель API ключа."""
    key_hash: str  # Хешированный ключ
    key_prefix: str  # Первые 8 символов для идентификации
    user_id: int
    name: str
    created_at: float
    expires_at: Optional[float] = None
    last_used_at: Optional[float] = None
    is_active: bool = True
    allowed_ips: List[str] = field(default_factory=list)
    rate_limit: int = 1000  # Запросов в минуту
    usage_count: int = 0
    
    def is_expired(self) -> bool:
        """Проверка истечения срока действия."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def is_valid(self) -> bool:
        """Проверка валидности ключа."""
        return self.is_active and not self.is_expired()
    
    def to_dict(self, include_hash: bool = False) -> Dict[str, Any]:
        """Конвертация в словарь (без полного хеша)."""
        data = {
            "key_prefix": self.key_prefix,
            "user_id": self.user_id,
            "name": self.name,
            "created_at": datetime.fromtimestamp(self.created_at).isoformat(),
            "expires_at": datetime.fromtimestamp(self.expires_at).isoformat() if self.expires_at else None,
            "last_used_at": datetime.fromtimestamp(self.last_used_at).isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
            "allowed_ips": self.allowed_ips,
            "rate_limit": self.rate_limit,
            "usage_count": self.usage_count,
        }
        if include_hash:
            data["key_hash"] = self.key_hash
        return data


class APIKeyManager:
    """Менеджер API ключей."""
    
    def __init__(self):
        # Хранилище: {user_id: {key_hash: APIKey}}
        self._keys: Dict[int, Dict[str, APIKey]] = {}
        self._lock = None  # asyncio.Lock для async версий
    
    def _hash_key(self, key: str) -> str:
        """Хеширование API ключа."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def _generate_key(self) -> str:
        """Генерация нового API ключа."""
        # Формат: rs_api_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        prefix = "rs_api_"
        random_part = secrets.token_hex(16)  # 32 символа
        return prefix + random_part
    
    def _get_key_prefix(self, key: str) -> str:
        """Получение префикса ключа (первые 8 символов после rs_api_)."""
        if key.startswith("rs_api_"):
            return key[8:16]
        return key[:8]
    
    def create_key(
        self,
        user_id: int,
        name: str,
        expires_in_days: Optional[int] = None,
        allowed_ips: Optional[List[str]] = None,
        rate_limit: int = 1000,
    ) -> tuple[str, APIKey]:
        """
        Создание нового API ключа.

        Args:
            user_id: ID пользователя
            name: Название ключа
            expires_in_days: Срок действия в днях (None = бессрочно)
            allowed_ips: Разрешённые IP адреса (None = все)
            rate_limit: Лимит запросов в минуту

        Returns:
            (plain_key, api_key) - полный ключ и объект APIKey
        """
        # Генерируем ключ
        plain_key = self._generate_key()
        key_hash = self._hash_key(plain_key)
        key_prefix = self._get_key_prefix(plain_key)
        
        now = time.time()
        expires_at = None
        if expires_in_days:
            expires_at = now + (expires_in_days * 24 * 60 * 60)
        
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            name=name,
            created_at=now,
            expires_at=expires_at,
            is_active=True,
            allowed_ips=allowed_ips or [],
            rate_limit=rate_limit,
        )
        
        # Сохраняем
        if user_id not in self._keys:
            self._keys[user_id] = {}
        self._keys[user_id][key_hash] = api_key
        
        return plain_key, api_key
    
    def verify_key(self, plain_key: str, ip: Optional[str] = None) -> Optional[APIKey]:
        """
        Проверка API ключа.

        Args:
            plain_key: Полный API ключ
            ip: IP адрес запроса

        Returns:
            APIKey если валиден, None иначе
        """
        if not plain_key or not plain_key.startswith("rs_api_"):
            return None
        
        key_hash = self._hash_key(plain_key)
        
        # Ищем ключ у всех пользователей
        for user_keys in self._keys.values():
            if key_hash in user_keys:
                api_key = user_keys[key_hash]
                
                # Проверяем валидность
                if not api_key.is_valid():
                    return None
                
                # Проверяем IP
                if ip and api_key.allowed_ips:
                    if ip not in api_key.allowed_ips:
                        return None
                
                # Обновляем last_used и usage_count
                api_key.last_used_at = time.time()
                api_key.usage_count += 1
                
                return api_key
        
        return None
    
    def revoke_key(self, user_id: int, key_hash: str) -> bool:
        """
        Отзыв API ключа.

        Args:
            user_id: ID пользователя
            key_hash: Хешированный ключ

        Returns:
            True если успешно
        """
        if user_id in self._keys and key_hash in self._keys[user_id]:
            self._keys[user_id][key_hash].is_active = False
            return True
        return False
    
    def rotate_key(
        self,
        user_id: int,
        old_key_hash: str,
        name: Optional[str] = None,
    ) -> Optional[tuple[str, APIKey]]:
        """
        Ротация API ключа.

        Args:
            user_id: ID пользователя
            old_key_hash: Хешированный старый ключ
            name: Название для нового ключа

        Returns:
            (plain_key, api_key) или None
        """
        if user_id not in self._keys or old_key_hash not in self._keys[user_id]:
            return None
        
        old_key = self._keys[user_id][old_key_hash]
        
        # Создаём новый ключ с теми же параметрами
        plain_key, new_key = self.create_key(
            user_id=user_id,
            name=name or f"{old_key.name} (rotated)",
            allowed_ips=old_key.allowed_ips,
            rate_limit=old_key.rate_limit,
        )
        
        # Отзываем старый ключ
        self.revoke_key(user_id, old_key_hash)
        
        return plain_key, new_key
    
    def get_keys_for_user(self, user_id: int) -> List[APIKey]:
        """Получить все ключи пользователя."""
        if user_id not in self._keys:
            return []
        return list(self._keys[user_id].values())
    
    def get_active_keys(self, user_id: int) -> List[APIKey]:
        """Получить активные ключи пользователя."""
        return [k for k in self.get_keys_for_user(user_id) if k.is_valid()]
    
    def delete_key(self, user_id: int, key_hash: str) -> bool:
        """Удалить ключ."""
        if user_id in self._keys and key_hash in self._keys[user_id]:
            del self._keys[user_id][key_hash]
            return True
        return False
    
    def get_usage_stats(self, user_id: int) -> Dict[str, Any]:
        """Получить статистику использования ключей."""
        keys = self.get_keys_for_user(user_id)
        
        total_usage = sum(k.usage_count for k in keys)
        active_keys = sum(1 for k in keys if k.is_valid())
        expired_keys = sum(1 for k in keys if k.is_expired())
        revoked_keys = sum(1 for k in keys if not k.is_active)
        
        return {
            "total_keys": len(keys),
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "revoked_keys": revoked_keys,
            "total_usage": total_usage,
        }


# Глобальный экземпляр
api_key_manager = APIKeyManager()


__all__ = [
    "api_key_manager",
    "APIKeyManager",
    "APIKey",
]
