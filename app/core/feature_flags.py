"""
Feature Flags система для управления функциональностью.

Поддерживает:
- Глобальные флаги (включено/выключено)
- Флаги для конкретных пользователей
- Флаги с процентным rollout
- Флаги с expiration date

Использование:
    from app.core.feature_flags import FeatureFlag, feature_flags
    
    if feature_flags.is_enabled("new_search_algorithm", user_id=123):
        # Использовать новый алгоритм
        pass
"""

import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Set
from dataclasses import dataclass, field
from enum import Enum
import json

from app.utils.logger import logger


class FlagType(str, Enum):
    """Типы feature флагов."""
    BOOLEAN = "boolean"  # Простой вкл/выкл
    PERCENTAGE = "percentage"  # Процентный rollout
    USER_LIST = "user_list"  # Список пользователей
    EXPERIMENT = "experiment"  # A/B тест


@dataclass
class FeatureFlag:
    """Feature флаг."""
    name: str
    enabled: bool = False
    flag_type: FlagType = FlagType.BOOLEAN
    description: str = ""
    
    # Для percentage rollout
    percentage: float = 0.0  # 0-100
    
    # Для user_list
    user_ids: Set[int] = field(default_factory=set)
    
    # Для expiration
    expires_at: Optional[datetime] = None
    
    # Метаданные
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    
    # Дополнительные параметры
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Проверяет истек ли флаг."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертирует в словарь."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "flag_type": self.flag_type.value,
            "description": self.description,
            "percentage": self.percentage,
            "user_ids": list(self.user_ids),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeatureFlag":
        """Создает из словаря."""
        return cls(
            name=data["name"],
            enabled=data.get("enabled", False),
            flag_type=FlagType(data.get("flag_type", "boolean")),
            description=data.get("description", ""),
            percentage=data.get("percentage", 0.0),
            user_ids=set(data.get("user_ids", [])),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            created_by=data.get("created_by"),
            metadata=data.get("metadata", {}),
        )


class FeatureFlagStore:
    """
    Хранилище feature флагов.
    
    Поддерживает in-memory и Redis хранилища.
    """
    
    def __init__(self, use_redis: bool = False, redis_client=None):
        self.use_redis = use_redis and redis_client is not None
        self.redis_client = redis_client
        
        # In-memory хранилище
        self._flags: Dict[str, FeatureFlag] = {}
        
        # История изменений
        self._history: List[Dict[str, Any]] = []
    
    def get(self, name: str) -> Optional[FeatureFlag]:
        """Получает флаг по имени."""
        if self.use_redis and self.redis_client:
            return self._get_from_redis(name)
        return self._flags.get(name)
    
    def set(self, flag: FeatureFlag) -> None:
        """Сохраняет флаг."""
        flag.updated_at = datetime.utcnow()
        
        if self.use_redis and self.redis_client:
            self._set_to_redis(flag)
        else:
            self._flags[flag.name] = flag
        
        # Логируем изменение
        self._log_change("set", flag)
        logger.info(f"Feature flag '{flag.name}' updated: enabled={flag.enabled}")
    
    def delete(self, name: str) -> None:
        """Удаляет флаг."""
        if self.use_redis and self.redis_client:
            self._delete_from_redis(name)
        else:
            self._flags.pop(name, None)
        
        self._log_change("delete", None, name=name)
        logger.info(f"Feature flag '{name}' deleted")
    
    def list_flags(self) -> List[FeatureFlag]:
        """Возвращает список всех флагов."""
        if self.use_redis and self.redis_client:
            return self._list_from_redis()
        return list(self._flags.values())
    
    def _get_from_redis(self, name: str) -> Optional[FeatureFlag]:
        """Получает флаг из Redis."""
        try:
            data = self.redis_client.get(f"feature_flag:{name}")
            if data:
                return FeatureFlag.from_dict(json.loads(data))
        except Exception as e:
            logger.error(f"Error getting feature flag from Redis: {e}")
        return None
    
    def _set_to_redis(self, flag: FeatureFlag) -> None:
        """Сохраняет флаг в Redis."""
        try:
            ttl = None
            if flag.expires_at:
                ttl = int((flag.expires_at - datetime.utcnow()).total_seconds())
                if ttl <= 0:
                    return
            
            data = json.dumps(flag.to_dict())
            self.redis_client.set(f"feature_flag:{flag.name}", data)
            
            if ttl:
                self.redis_client.expire(f"feature_flag:{flag.name}", ttl)
        except Exception as e:
            logger.error(f"Error setting feature flag in Redis: {e}")
    
    def _delete_from_redis(self, name: str) -> None:
        """Удаляет флаг из Redis."""
        try:
            self.redis_client.delete(f"feature_flag:{name}")
        except Exception as e:
            logger.error(f"Error deleting feature flag from Redis: {e}")
    
    def _list_from_redis(self) -> List[FeatureFlag]:
        """Получает список всех флагов из Redis."""
        flags = []
        try:
            keys = self.redis_client.keys("feature_flag:*")
            for key in keys:
                data = self.redis_client.get(key)
                if data:
                    flags.append(FeatureFlag.from_dict(json.loads(data)))
        except Exception as e:
            logger.error(f"Error listing feature flags from Redis: {e}")
        return flags
    
    def _log_change(self, action: str, flag: Optional[FeatureFlag], name: Optional[str] = None) -> None:
        """Логирует изменение флага."""
        self._history.append({
            "action": action,
            "flag_name": flag.name if flag else name,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Возвращает историю изменений."""
        return self._history[-limit:]


class FeatureFlags:
    """
    Менеджер feature флагов.
    
    Предоставляет удобный API для проверки флагов.
    """
    
    def __init__(self, store: Optional[FeatureFlagStore] = None):
        self.store = store or FeatureFlagStore()
        
        # Кэш для производительности
        self._cache: Dict[str, tuple] = {}  # {name: (value, timestamp)}
        self._cache_ttl = 60  # секунд
    
    def initialize(self) -> None:
        """Инициализирует флаги по умолчанию."""
        default_flags = [
            FeatureFlag(
                name="new_search_algorithm",
                enabled=False,
                flag_type=FlagType.PERCENTAGE,
                percentage=10.0,
                description="Новый алгоритм поиска (10% rollout)",
            ),
            FeatureFlag(
                name="premium_features",
                enabled=False,
                flag_type=FlagType.USER_LIST,
                description="Premium функции для избранных пользователей",
            ),
            FeatureFlag(
                name="dark_mode",
                enabled=True,
                flag_type=FlagType.BOOLEAN,
                description="Тёмная тема интерфейса",
            ),
            FeatureFlag(
                name="beta_api",
                enabled=False,
                flag_type=FlagType.BOOLEAN,
                description="Beta версия API",
                expires_at=datetime.utcnow() + timedelta(days=30),
            ),
        ]
        
        for flag in default_flags:
            if not self.store.get(flag.name):
                self.store.set(flag)
    
    def is_enabled(
        self,
        name: str,
        user_id: Optional[int] = None,
        check_cache: bool = True
    ) -> bool:
        """
        Проверяет включен ли флаг.
        
        Args:
            name: Имя флага
            user_id: ID пользователя для персонализированных флагов
            check_cache: Проверять ли кэш
        
        Returns:
            True если флаг включен
        """
        # Проверяем кэш
        if check_cache:
            cached = self._get_from_cache(name, user_id)
            if cached is not None:
                return cached
        
        # Получаем флаг
        flag = self.store.get(name)
        if flag is None:
            logger.debug(f"Feature flag '{name}' not found, defaulting to False")
            return False
        
        # Проверяем истечение
        if flag.is_expired():
            logger.info(f"Feature flag '{name}' expired, disabling")
            return False
        
        # Проверяем глобальное включение
        if not flag.enabled:
            self._save_to_cache(name, user_id, False)
            return False
        
        # Проверяем в зависимости от типа
        result = self._check_flag(flag, user_id)
        self._save_to_cache(name, user_id, result)
        return result
    
    def _check_flag(self, flag: FeatureFlag, user_id: Optional[int]) -> bool:
        """Проверяет флаг в зависимости от типа."""
        if flag.flag_type == FlagType.BOOLEAN:
            return flag.enabled
        
        elif flag.flag_type == FlagType.PERCENTAGE:
            # Процентный rollout на основе hash от user_id
            if user_id is None:
                # Для анонимов используем 50% от процента
                return False
            
            # Детерминированный hash
            hash_value = int(hashlib.md5(f"{flag.name}:{user_id}".encode()).hexdigest(), 16) % 100
            return hash_value < flag.percentage
        
        elif flag.flag_type == FlagType.USER_LIST:
            return user_id in flag.user_ids if user_id is not None else False
        
        elif flag.flag_type == FlagType.EXPERIMENT:
            # A/B тест
            if user_id is None:
                return False
            
            hash_value = int(hashlib.md5(f"exp:{flag.name}:{user_id}".encode()).hexdigest(), 16) % 100
            control_percentage = flag.metadata.get("control_percentage", 50)
            return hash_value >= control_percentage
        
        return False
    
    def _get_from_cache(self, name: str, user_id: Optional[int]) -> Optional[bool]:
        """Получает значение из кэша."""
        cache_key = f"{name}:{user_id}"
        if cache_key in self._cache:
            value, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return value
        return None
    
    def _save_to_cache(self, name: str, user_id: Optional[int], value: bool) -> None:
        """Сохраняет значение в кэш."""
        cache_key = f"{name}:{user_id}"
        self._cache[cache_key] = (value, time.time())
    
    def enable(self, name: str) -> None:
        """Включает флаг."""
        flag = self.store.get(name)
        if flag:
            flag.enabled = True
            self.store.set(flag)
            # Очищаем кэш
            self._clear_cache(name)
        else:
            raise ValueError(f"Feature flag '{name}' not found")
    
    def disable(self, name: str) -> None:
        """Выключает флаг."""
        flag = self.store.get(name)
        if flag:
            flag.enabled = False
            self.store.set(flag)
            # Очищаем кэш
            self._clear_cache(name)
        else:
            raise ValueError(f"Feature flag '{name}' not found")
    
    def _clear_cache(self, name: str) -> None:
        """Очищает кэш для флага."""
        keys_to_delete = [key for key in self._cache if key.startswith(f"{name}:")]
        for key in keys_to_delete:
            del self._cache[key]
    
    def create_flag(
        self,
        name: str,
        enabled: bool = False,
        flag_type: str = "boolean",
        description: str = "",
        percentage: float = 0.0,
        user_ids: Optional[List[int]] = None,
        expires_in_days: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FeatureFlag:
        """Создает новый флаг."""
        flag = FeatureFlag(
            name=name,
            enabled=enabled,
            flag_type=FlagType(flag_type),
            description=description,
            percentage=percentage,
            user_ids=set(user_ids) if user_ids else set(),
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None,
            metadata=metadata or {},
        )
        self.store.set(flag)
        return flag
    
    def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """Получает флаг по имени."""
        return self.store.get(name)
    
    def list_flags(self) -> List[FeatureFlag]:
        """Возвращает список всех флагов."""
        return self.store.list_flags()
    
    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику по флагам."""
        flags = self.list_flags()
        return {
            "total_flags": len(flags),
            "enabled_flags": sum(1 for f in flags if f.enabled),
            "disabled_flags": sum(1 for f in flags if not f.enabled),
            "expired_flags": sum(1 for f in flags if f.is_expired()),
            "by_type": {
                flag_type.value: sum(1 for f in flags if f.flag_type == flag_type)
                for flag_type in FlagType
            },
        }


# Глобальный экземпляр
feature_flags = FeatureFlags()


__all__ = [
    "FeatureFlag",
    "FeatureFlagStore",
    "FeatureFlags",
    "FlagType",
    "feature_flags",
]
