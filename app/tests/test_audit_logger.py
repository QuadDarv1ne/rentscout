"""
Тесты для Audit Logger.
"""
import pytest
import json
import os
from app.utils.audit_logger import (
    audit_logger,
    AuditLogger,
    AuditEvent,
    AuditEventType,
    AuditSeverity,
)


class TestAuditEventType:
    """Тесты типов событий."""

    def test_auth_events(self):
        """Тест событий аутентификации."""
        assert AuditEventType.AUTH_LOGIN_SUCCESS.value == "auth.login.success"
        assert AuditEventType.AUTH_LOGIN_FAILED.value == "auth.login.failed"
        assert AuditEventType.AUTH_2FA_ENABLED.value == "auth.2fa.enabled"

    def test_user_events(self):
        """Тест событий пользователей."""
        assert AuditEventType.USER_CREATED.value == "user.created"
        assert AuditEventType.USER_UPDATED.value == "user.updated"

    def test_security_events(self):
        """Тест событий безопасности."""
        assert AuditEventType.SECURITY_VIOLATION.value == "security.violation"
        assert AuditEventType.RATE_LIMIT_EXCEEDED.value == "rate.limit.exceeded"


class TestAuditSeverity:
    """Тесты уровней важности."""

    def test_severity_values(self):
        """Тест значений уровней."""
        assert AuditSeverity.DEBUG.value == "debug"
        assert AuditSeverity.INFO.value == "info"
        assert AuditSeverity.WARNING.value == "warning"
        assert AuditSeverity.ERROR.value == "error"
        assert AuditSeverity.CRITICAL.value == "critical"


class TestAuditEvent:
    """Тесты события аудита."""

    def test_event_creation(self):
        """Тест создания события."""
        event = AuditEvent(
            event_id="audit_test_001",
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            severity=AuditSeverity.INFO,
            timestamp=1234567890.0,
            user_id=1,
            username="testuser",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            resource_type="user",
            resource_id=1,
            action="login",
            status="success",
        )
        
        assert event.event_id == "audit_test_001"
        assert event.user_id == 1
        assert event.username == "testuser"
        assert event.status == "success"

    def test_event_to_dict(self):
        """Тест конвертации в словарь."""
        event = AuditEvent(
            event_id="audit_test_002",
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            severity=AuditSeverity.INFO,
            timestamp=1234567890.0,
            user_id=1,
            username="testuser",
            ip_address="192.168.1.1",
            user_agent=None,
            resource_type=None,
            resource_id=None,
            action="login",
            status="success",
            details={"method": "password"},
        )
        
        data = event.to_dict()
        
        assert data["event_id"] == "audit_test_002"
        assert data["event_type"] == "auth.login.success"
        assert data["severity"] == "info"
        assert data["user_id"] == 1
        assert data["username"] == "testuser"
        assert "timestamp_iso" in data
        assert data["details"]["method"] == "password"

    def test_event_to_json(self):
        """Тест конвертации в JSON."""
        event = AuditEvent(
            event_id="audit_test_003",
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            severity=AuditSeverity.INFO,
            timestamp=1234567890.0,
            user_id=1,
            username="testuser",
            ip_address="192.168.1.1",
            user_agent=None,
            resource_type=None,
            resource_id=None,
            action="login",
            status="success",
        )
        
        json_str = event.to_json()
        data = json.loads(json_str)
        
        assert data["event_id"] == "audit_test_003"
        assert isinstance(json_str, str)


class TestAuditLogger:
    """Тесты логгера аудита."""

    def test_log_auth_login_success(self):
        """Тест логирования успешного входа."""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        event = logger.log_auth_login(
            user_id=1,
            username="testuser",
            success=True,
            ip="192.168.1.1"
        )
        
        assert event.event_type == AuditEventType.AUTH_LOGIN_SUCCESS
        assert event.status == "success"
        assert event.user_id == 1

    def test_log_auth_login_failed(self):
        """Тест логирования неудачного входа."""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        event = logger.log_auth_login(
            user_id=1,
            username="testuser",
            success=False,
            ip="192.168.1.1",
            reason="Invalid password"
        )
        
        assert event.event_type == AuditEventType.AUTH_LOGIN_FAILED
        assert event.status == "failure"
        assert event.details["reason"] == "Invalid password"

    def test_log_auth_2fa_success(self):
        """Тест логирования успешного 2FA."""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        event = logger.log_auth_2fa(
            user_id=1,
            username="testuser",
            success=True,
            ip="192.168.1.1"
        )
        
        assert event.event_type == AuditEventType.AUTH_2FA_VERIFIED
        assert event.status == "success"

    def test_log_auth_2fa_failed(self):
        """Тест логирования неудачного 2FA."""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        event = logger.log_auth_2fa(
            user_id=1,
            username="testuser",
            success=False,
            ip="192.168.1.1"
        )
        
        assert event.event_type == AuditEventType.AUTH_2FA_FAILED
        assert event.status == "failure"

    def test_log_api_key_usage(self):
        """Тест логирования использования API ключа."""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        event = logger.log_api_key_usage(
            user_id=1,
            key_prefix="abc12345",
            ip="192.168.1.1",
            endpoint="/api/properties"
        )
        
        assert event.event_type == AuditEventType.API_KEY_USED
        assert event.details["key_prefix"] == "abc12345"
        assert event.details["endpoint"] == "/api/properties"

    def test_log_security_violation(self):
        """Тест логирования нарушения безопасности."""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        event = logger.log_security_violation(
            user_id=1,
            ip="192.168.1.1",
            violation_type="sql_injection_attempt",
            details={"payload": "'; DROP TABLE users;--"}
        )
        
        assert event.event_type == AuditEventType.SECURITY_VIOLATION
        assert event.severity == AuditSeverity.CRITICAL
        assert event.status == "denied"

    def test_log_data_access(self):
        """Тест логирования доступа к данным."""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        event = logger.log_data_access(
            user_id=1,
            resource_type="property",
            resource_id=123,
            ip="192.168.1.1",
            action="read"
        )
        
        assert event.event_type == AuditEventType.DATA_ACCESSED
        assert event.resource_type == "property"
        assert event.resource_id == 123

    def test_log_admin_action(self):
        """Тест логирования админ действия."""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        event = logger.log_admin_action(
            user_id=1,
            username="admin",
            action="user_delete",
            details={"deleted_user_id": 999},
            ip="192.168.1.1"
        )
        
        assert event.event_type == AuditEventType.ADMIN_ACTION
        assert event.details["deleted_user_id"] == 999

    def test_event_id_generation(self):
        """Тест генерации ID событий."""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        event1 = logger.log(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            user_id=1,
            username="user1",
            ip_address="192.168.1.1",
            action="login",
        )
        
        event2 = logger.log(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            user_id=2,
            username="user2",
            ip_address="192.168.1.2",
            action="login",
        )
        
        assert event1.event_id != event2.event_id
        assert event1.event_id.startswith("audit_")
        assert event2.event_id.startswith("audit_")

    def test_severity_assignment(self):
        """Тест назначения уровня важности."""
        logger = AuditLogger(log_file="logs/test_audit.log")
        
        # Critical
        event = logger.log(event_type=AuditEventType.SECURITY_VIOLATION)
        assert event.severity == AuditSeverity.CRITICAL
        
        # Warning
        event = logger.log(event_type=AuditEventType.AUTH_LOGIN_FAILED)
        assert event.severity == AuditSeverity.WARNING
        
        # Info
        event = logger.log(event_type=AuditEventType.AUTH_LOGIN_SUCCESS)
        assert event.severity == AuditSeverity.INFO


class TestAuditLoggerFileOutput:
    """Тесты вывода в файл."""

    def test_log_file_creation(self):
        """Тест создания файла лога."""
        test_log = "logs/test_audit_output.log"
        logger = AuditLogger(log_file=test_log)
        
        logger.log(
            event_type=AuditEventType.AUTH_LOGIN_SUCCESS,
            user_id=1,
            username="testuser",
            ip_address="192.168.1.1",
            action="login",
        )
        
        # Проверяем что файл существует
        assert os.path.exists(test_log)
        
        # Проверяем содержимое
        with open(test_log, 'r', encoding='utf-8') as f:
            content = f.read()
            assert "auth.login.success" in content
            assert "testuser" in content
        
        # Cleanup
        os.remove(test_log)

    def test_log_json_format(self):
        """Тест JSON формата логов."""
        test_log = "logs/test_audit_json.log"
        logger = AuditLogger(log_file=test_log)
        
        logger.log(
            event_type=AuditEventType.USER_CREATED,
            user_id=1,
            username="newuser",
            ip_address="192.168.1.1",
            action="create",
        )
        
        with open(test_log, 'r', encoding='utf-8') as f:
            line = f.readline()
            data = json.loads(line)  # Должен быть валидный JSON
            
            assert "event_id" in data
            assert "timestamp" in data
            assert "event_type" in data
        
        # Cleanup
        os.remove(test_log)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
