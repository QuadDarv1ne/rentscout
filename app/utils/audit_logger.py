"""
Audit Logging System.

Логирование всех критических операций:
- Аутентификация (вход, выход, 2FA)
- Изменение данных пользователей
- Доступ к чувствительным данным
- Административные операции
- API ключи
"""

import json
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib


class AuditEventType(str, Enum):
    """Типы событий аудита."""
    # Аутентификация
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILED = "auth.login.failed"
    AUTH_LOGOUT = "auth.logout"
    AUTH_2FA_ENABLED = "auth.2fa.enabled"
    AUTH_2FA_DISABLED = "auth.2fa.disabled"
    AUTH_2FA_VERIFIED = "auth.2fa.verified"
    AUTH_2FA_FAILED = "auth.2fa.failed"
    AUTH_PASSWORD_CHANGED = "auth.password.changed"
    AUTH_PASSWORD_RESET = "auth.password.reset"
    
    # Пользователи
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_ROLE_CHANGED = "user.role.changed"
    
    # API ключи
    API_KEY_CREATED = "api.key.created"
    API_KEY_REVOKED = "api.key.revoked"
    API_KEY_ROTATED = "api.key.rotated"
    API_KEY_USED = "api.key.used"
    
    # Данные
    DATA_ACCESSED = "data.accessed"
    DATA_CREATED = "data.created"
    DATA_UPDATED = "data.updated"
    DATA_DELETED = "data.deleted"
    
    # Админ операции
    ADMIN_ACTION = "admin.action"
    CONFIG_CHANGED = "config.changed"
    
    # Безопасность
    SECURITY_VIOLATION = "security.violation"
    RATE_LIMIT_EXCEEDED = "rate.limit.exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious.activity"


class AuditSeverity(str, Enum):
    """Уровень важности события."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Событие аудита."""
    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: float
    user_id: Optional[int]
    username: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[int]
    action: str
    status: str  # success, failure, denied
    details: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "user_id": self.user_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "status": self.status,
            "details": self.details,
            "request_id": self.request_id,
        }
    
    def to_json(self) -> str:
        """Конвертация в JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AuditLogger:
    """Логгер аудита."""
    
    def __init__(self, log_file: str = "logs/audit.log"):
        self.log_file = log_file
        self._event_counter = 0
        self._buffer: List[AuditEvent] = []
        self._buffer_size = 100
        
        # Настраиваем logger
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        
        # File handler
        try:
            handler = logging.FileHandler(log_file, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(handler)
        except Exception:
            # Если файл недоступен, используем только console
            pass
    
    def _generate_event_id(self) -> str:
        """Генерация уникального ID события."""
        self._event_counter += 1
        timestamp = str(int(time.time() * 1000))
        counter = str(self._event_counter).zfill(6)
        return f"audit_{timestamp}_{counter}"
    
    def _get_severity_for_event(self, event_type: AuditEventType) -> AuditSeverity:
        """Определение важности для типа события."""
        if event_type in (AuditEventType.SECURITY_VIOLATION, AuditEventType.SUSPICIOUS_ACTIVITY):
            return AuditSeverity.CRITICAL
        elif event_type in (AuditEventType.AUTH_LOGIN_FAILED, AuditEventType.RATE_LIMIT_EXCEEDED):
            return AuditSeverity.WARNING
        elif event_type in (AuditEventType.DATA_DELETED, AuditEventType.USER_DELETED):
            return AuditSeverity.ERROR
        elif "failed" in event_type.value or "denied" in event_type.value:
            return AuditSeverity.WARNING
        else:
            return AuditSeverity.INFO
    
    def log(
        self,
        event_type: AuditEventType,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        action: Optional[str] = None,
        status: str = "success",
        details: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
    ) -> AuditEvent:
        """
        Логирование события.

        Args:
            event_type: Тип события
            user_id: ID пользователя
            username: Имя пользователя
            ip_address: IP адрес
            user_agent: User agent
            resource_type: Тип ресурса
            resource_id: ID ресурса
            action: Действие
            status: Статус (success, failure, denied)
            details: Дополнительные данные
            request_id: ID запроса

        Returns:
            AuditEvent
        """
        event = AuditEvent(
            event_id=self._generate_event_id(),
            event_type=event_type,
            severity=self._get_severity_for_event(event_type),
            timestamp=time.time(),
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action or event_type.value,
            status=status,
            details=details or {},
            request_id=request_id,
        )
        
        # Логируем
        self._log_event(event)
        
        # Буферизация для batch записи
        self._buffer.append(event)
        if len(self._buffer) >= self._buffer_size:
            self.flush()
        
        return event
    
    def _log_event(self, event: AuditEvent):
        """Запись события в лог."""
        self.logger.info(event.to_json())
    
    def flush(self):
        """Сброс буфера."""
        self._buffer.clear()
    
    # === Convenience методы для частых событий ===
    
    def log_auth_login(self, user_id: int, username: str, success: bool, ip: str, 
                       reason: Optional[str] = None):
        """Логирование входа."""
        event_type = AuditEventType.AUTH_LOGIN_SUCCESS if success else AuditEventType.AUTH_LOGIN_FAILED
        status = "success" if success else "failure"
        details = {"reason": reason} if reason else {}
        
        self.log(
            event_type=event_type,
            user_id=user_id,
            username=username,
            ip_address=ip,
            action="login",
            status=status,
            details=details,
        )
    
    def log_auth_2fa(self, user_id: int, username: str, success: bool, ip: str):
        """Логирование 2FA."""
        event_type = AuditEventType.AUTH_2FA_VERIFIED if success else AuditEventType.AUTH_2FA_FAILED
        self.log(
            event_type=event_type,
            user_id=user_id,
            username=username,
            ip_address=ip,
            action="2fa_verify",
            status="success" if success else "failure",
        )
    
    def log_api_key_usage(self, user_id: int, key_prefix: str, ip: str, endpoint: str):
        """Логирование использования API ключа."""
        self.log(
            event_type=AuditEventType.API_KEY_USED,
            user_id=user_id,
            ip_address=ip,
            resource_type="api_key",
            action=f"api_request:{endpoint}",
            status="success",
            details={"key_prefix": key_prefix, "endpoint": endpoint},
        )
    
    def log_security_violation(self, user_id: Optional[int], ip: str, 
                                violation_type: str, details: Dict[str, Any]):
        """Логирование нарушения безопасности."""
        self.log(
            event_type=AuditEventType.SECURITY_VIOLATION,
            user_id=user_id,
            username=details.get("username"),
            ip_address=ip,
            action=violation_type,
            status="denied",
            details=details,
        )
    
    def log_data_access(self, user_id: int, resource_type: str, resource_id: int, 
                        ip: str, action: str = "read"):
        """Логирование доступа к данным."""
        self.log(
            event_type=AuditEventType.DATA_ACCESSED,
            user_id=user_id,
            ip_address=ip,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            status="success",
        )
    
    def log_admin_action(self, user_id: int, username: str, action: str, 
                         details: Dict[str, Any], ip: str):
        """Логирование административного действия."""
        self.log(
            event_type=AuditEventType.ADMIN_ACTION,
            user_id=user_id,
            username=username,
            ip_address=ip,
            action=action,
            status="success",
            details=details,
        )


# Глобальный экземпляр
audit_logger = AuditLogger()


__all__ = [
    "audit_logger",
    "AuditLogger",
    "AuditEvent",
    "AuditEventType",
    "AuditSeverity",
]
