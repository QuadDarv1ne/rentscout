"""
Tests for audit logging system.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.core.audit_log import (
    AuditLogger,
    AuditLogStorage,
    AuditLogEntry,
    AuditEventType,
    RiskLevel,
    audit_logger,
)


class TestAuditEventType:
    """Tests for AuditEventType enum."""

    def test_event_type_values(self):
        """Test event type values."""
        assert AuditEventType.AUTH_LOGIN.value == "auth.login"
        assert AuditEventType.AUTH_LOGOUT.value == "auth.logout"
        assert AuditEventType.PROPERTY_CREATED.value == "property.created"
        assert AuditEventType.USER_DELETED.value == "user.deleted"


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_level_values(self):
        """Test risk level values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestAuditLogEntry:
    """Tests for AuditLogEntry dataclass."""

    def test_create_entry(self):
        """Test creating audit log entry."""
        entry = AuditLogEntry(
            id="test_1",
            timestamp=datetime.utcnow(),
            user_id=123,
            action=AuditEventType.AUTH_LOGIN,
            resource_type=None,
            resource_id=None,
            ip_address="192.168.1.1",
            user_agent="Test Browser",
            details={},
            risk_level=RiskLevel.LOW,
            status="success"
        )
        assert entry.id == "test_1"
        assert entry.user_id == 123
        assert entry.action == AuditEventType.AUTH_LOGIN

    def test_entry_to_dict(self):
        """Test entry to_dict."""
        entry = AuditLogEntry(
            id="test_1",
            timestamp=datetime.utcnow(),
            user_id=123,
            action=AuditEventType.AUTH_LOGIN,
            resource_type=None,
            resource_id=None,
            ip_address="192.168.1.1",
            user_agent="Test",
            details={},
            risk_level=RiskLevel.LOW,
            status="success"
        )
        data = entry.to_dict()
        assert "id" in data
        assert "timestamp" in data
        assert data["user_id"] == 123
        assert data["action"] == "auth.login"
        assert data["risk_level"] == "low"

    def test_entry_to_json(self):
        """Test entry to_json."""
        entry = AuditLogEntry(
            id="test_1",
            timestamp=datetime.utcnow(),
            user_id=123,
            action=AuditEventType.AUTH_LOGIN,
            resource_type=None,
            resource_id=None,
            ip_address="192.168.1.1",
            user_agent="Test",
            details={},
            risk_level=RiskLevel.LOW,
            status="success"
        )
        json_str = entry.to_json()
        assert "test_1" in json_str
        assert "auth.login" in json_str


@pytest.mark.asyncio
class TestAuditLogStorage:
    """Tests for AuditLogStorage."""

    async def test_store_entry(self):
        """Test storing entry."""
        storage = AuditLogStorage()
        entry = AuditLogEntry(
            id="test_1",
            timestamp=datetime.utcnow(),
            user_id=123,
            action=AuditEventType.AUTH_LOGIN,
            resource_type=None,
            resource_id=None,
            ip_address="192.168.1.1",
            user_agent="Test",
            details={},
            risk_level=RiskLevel.LOW,
            status="success"
        )
        await storage.store(entry)
        assert len(storage._entries) == 1

    async def test_get_entries(self):
        """Test getting entries."""
        storage = AuditLogStorage()
        
        # Add entries
        for i in range(5):
            entry = AuditLogEntry(
                id=f"test_{i}",
                timestamp=datetime.utcnow(),
                user_id=123,
                action=AuditEventType.AUTH_LOGIN,
                resource_type=None,
                resource_id=None,
                ip_address="192.168.1.1",
                user_agent="Test",
                details={},
                risk_level=RiskLevel.LOW,
                status="success"
            )
            await storage.store(entry)
        
        entries = await storage.get_entries(user_id=123)
        assert len(entries) == 5

    async def test_get_entries_filter_by_action(self):
        """Test filtering by action."""
        storage = AuditLogStorage()
        
        entry1 = AuditLogEntry(
            id="test_1",
            timestamp=datetime.utcnow(),
            user_id=123,
            action=AuditEventType.AUTH_LOGIN,
            resource_type=None,
            resource_id=None,
            ip_address="192.168.1.1",
            user_agent="Test",
            details={},
            risk_level=RiskLevel.LOW,
            status="success"
        )
        entry2 = AuditLogEntry(
            id="test_2",
            timestamp=datetime.utcnow(),
            user_id=123,
            action=AuditEventType.PROPERTY_CREATED,
            resource_type=None,
            resource_id=None,
            ip_address="192.168.1.1",
            user_agent="Test",
            details={},
            risk_level=RiskLevel.MEDIUM,
            status="success"
        )
        await storage.store(entry1)
        await storage.store(entry2)
        
        entries = await storage.get_entries(action="auth.login")
        assert len(entries) == 1
        assert entries[0].action == AuditEventType.AUTH_LOGIN

    async def test_get_entries_pagination(self):
        """Test pagination."""
        storage = AuditLogStorage()
        
        for i in range(20):
            entry = AuditLogEntry(
                id=f"test_{i}",
                timestamp=datetime.utcnow(),
                user_id=123,
                action=AuditEventType.AUTH_LOGIN,
                resource_type=None,
                resource_id=None,
                ip_address="192.168.1.1",
                user_agent="Test",
                details={},
                risk_level=RiskLevel.LOW,
                status="success"
            )
            await storage.store(entry)
        
        entries_page1 = await storage.get_entries(limit=10, offset=0)
        entries_page2 = await storage.get_entries(limit=10, offset=10)
        
        assert len(entries_page1) == 10
        assert len(entries_page2) == 10

    async def test_get_stats(self):
        """Test getting statistics."""
        storage = AuditLogStorage()
        
        entry = AuditLogEntry(
            id="test_1",
            timestamp=datetime.utcnow(),
            user_id=123,
            action=AuditEventType.AUTH_LOGIN,
            resource_type=None,
            resource_id=None,
            ip_address="192.168.1.1",
            user_agent="Test",
            details={},
            risk_level=RiskLevel.LOW,
            status="success"
        )
        await storage.store(entry)
        
        stats = await storage.get_stats()
        assert "total_entries" in stats
        assert "entries_last_24h" in stats
        assert "unique_users" in stats
        assert "by_risk_level" in stats

    async def test_cleanup_old_entries(self):
        """Test cleaning up old entries."""
        storage = AuditLogStorage(retention_days=1)
        
        # Add entry with old timestamp
        old_timestamp = datetime.utcnow() - timedelta(days=2)
        entry = AuditLogEntry(
            id="old_entry",
            timestamp=old_timestamp,
            user_id=123,
            action=AuditEventType.AUTH_LOGIN,
            resource_type=None,
            resource_id=None,
            ip_address="192.168.1.1",
            user_agent="Test",
            details={},
            risk_level=RiskLevel.LOW,
            status="success"
        )
        await storage.store(entry)
        
        # Cleanup should remove old entry
        removed = await storage.cleanup_old_entries()
        assert removed == 1
        assert len(storage._entries) == 0


@pytest.mark.asyncio
class TestAuditLogger:
    """Tests for AuditLogger."""

    async def test_init(self):
        """Test initialization."""
        logger = AuditLogger()
        assert logger.storage is not None
        assert logger._entry_count == 0

    async def test_log_action(self):
        """Test logging action."""
        logger = AuditLogger(async_write=False)
        
        entry = await logger.log_action(
            action=AuditEventType.AUTH_LOGIN,
            user_id=123,
            ip_address="192.168.1.1",
            status="success"
        )
        
        assert entry is not None
        assert entry.user_id == 123
        assert entry.action == AuditEventType.AUTH_LOGIN
        assert logger._entry_count == 1

    async def test_log_action_with_resource(self):
        """Test logging action with resource."""
        logger = AuditLogger(async_write=False)
        
        entry = await logger.log_action(
            action=AuditEventType.PROPERTY_CREATED,
            user_id=123,
            resource_type="property",
            resource_id=456,
            details={"price": 50000},
            status="success"
        )
        
        assert entry.resource_type == "property"
        assert entry.resource_id == 456
        assert entry.details["price"] == 50000

    async def test_log_action_risk_level(self):
        """Test risk level assignment."""
        logger = AuditLogger(async_write=False)
        
        # Low risk
        entry1 = await logger.log_action(
            action=AuditEventType.AUTH_LOGIN,
            user_id=123
        )
        assert entry1.risk_level == RiskLevel.LOW
        
        # High risk
        entry2 = await logger.log_action(
            action=AuditEventType.AUTH_FAILED,
            user_id=123
        )
        assert entry2.risk_level == RiskLevel.HIGH
        
        # Critical risk
        entry3 = await logger.log_action(
            action=AuditEventType.USER_DELETED,
            user_id=123
        )
        assert entry3.risk_level == RiskLevel.CRITICAL

    async def test_get_audit_trail(self):
        """Test getting audit trail."""
        logger = AuditLogger(async_write=False)
        
        # Log multiple actions
        for i in range(5):
            await logger.log_action(
                action=AuditEventType.AUTH_LOGIN,
                user_id=123
            )
        
        trail = await logger.get_audit_trail(user_id=123, limit=10)
        assert len(trail) == 5

    async def test_get_stats(self):
        """Test getting statistics."""
        logger = AuditLogger(async_write=False)
        
        await logger.log_action(
            action=AuditEventType.AUTH_LOGIN,
            user_id=123
        )
        
        stats = await logger.get_stats()
        assert "entry_count" in stats
        assert stats["entry_count"] == 1

    async def test_async_write(self):
        """Test async write mode."""
        logger = AuditLogger(async_write=True)
        await logger.start()
        
        try:
            await logger.log_action(
                action=AuditEventType.AUTH_LOGIN,
                user_id=123
            )
            
            # Give time for async processing
            await asyncio.sleep(0.5)
            
            assert logger._entry_count == 1
        finally:
            await logger.stop()


class TestGlobalAuditLogger:
    """Tests for global audit logger instance."""

    def test_global_instance_exists(self):
        """Test global instance exists."""
        assert audit_logger is not None
        assert isinstance(audit_logger, AuditLogger)


class TestAuditIntegration:
    """Integration tests for audit logging."""

    @pytest.mark.asyncio
    async def test_full_audit_workflow(self):
        """Test complete audit workflow."""
        logger = AuditLogger(async_write=False)
        
        # User logs in
        await logger.log_action(
            action=AuditEventType.AUTH_LOGIN,
            user_id=123,
            ip_address="192.168.1.1",
            status="success"
        )
        
        # User creates property
        await logger.log_action(
            action=AuditEventType.PROPERTY_CREATED,
            user_id=123,
            resource_type="property",
            resource_id=456,
            details={"price": 50000},
            status="success"
        )
        
        # User logs out
        await logger.log_action(
            action=AuditEventType.AUTH_LOGOUT,
            user_id=123,
            status="success"
        )
        
        # Get audit trail
        trail = await logger.get_audit_trail(user_id=123)
        assert len(trail) == 3
        
        # Get stats
        stats = await logger.get_stats()
        assert stats["entry_count"] == 3
        assert stats["unique_users"] == 1

    @pytest.mark.asyncio
    async def test_security_event_logging(self):
        """Test security event logging."""
        logger = AuditLogger(async_write=False)
        
        # Log failed login attempts
        for i in range(3):
            await logger.log_action(
                action=AuditEventType.AUTH_FAILED,
                user_id=999,
                ip_address="10.0.0.1",
                status="failure",
                details={"reason": "invalid_password"}
            )
        
        # Log security alert (risk level is auto-assigned based on action)
        await logger.log_action(
            action=AuditEventType.SECURITY_ALERT,
            user_id=999,
            details={"alert": "multiple_failed_logins"},
            status="warning"
        )
        
        # Get events
        trail = await logger.get_audit_trail(
            start_date=datetime.utcnow() - timedelta(hours=1)
        )
        assert len(trail) >= 4
        
        # Check that SECURITY_ALERT has CRITICAL risk level
        alert_entry = [e for e in trail if e.action == AuditEventType.SECURITY_ALERT]
        if alert_entry:
            assert alert_entry[0].risk_level == RiskLevel.CRITICAL
