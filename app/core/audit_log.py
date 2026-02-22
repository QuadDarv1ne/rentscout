"""
Audit Logging System for RentScout.

Features:
- User action tracking
- Security event logging
- Data change tracking
- Compliance reporting
- Searchable audit trail

Usage:
    from app.core.audit_log import audit_logger
    
    # Log user action
    await audit_logger.log_action(
        user_id=123,
        action="property.create",
        resource_type="property",
        resource_id=456,
        details={"price": 50000}
    )
    
    # Get audit trail
    logs = await audit_logger.get_audit_trail(
        user_id=123,
        start_date=datetime.utcnow() - timedelta(days=7)
    )
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import logging
import hashlib
from collections import deque

from app.utils.logger import logger


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_2FA_ENABLED = "auth.2fa_enabled"
    AUTH_2FA_DISABLED = "auth.2fa_disabled"
    
    # User management
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"
    USER_PASSWORD_CHANGED = "user.password_changed"
    
    # API keys
    API_KEY_CREATED = "api_key.created"
    API_KEY_REVOKED = "api_key.revoked"
    API_KEY_USED = "api_key.used"
    
    # Properties
    PROPERTY_CREATED = "property.created"
    PROPERTY_UPDATED = "property.updated"
    PROPERTY_DELETED = "property.deleted"
    PROPERTY_VIEWED = "property.viewed"
    
    # Data export
    DATA_EXPORTED = "data.exported"
    DATA_IMPORTED = "data.imported"
    
    # System
    CONFIG_CHANGED = "system.config_changed"
    PERMISSION_CHANGED = "system.permission_changed"
    SECURITY_ALERT = "system.security_alert"


class RiskLevel(str, Enum):
    """Risk level of audit events."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditLogEntry:
    """Audit log entry."""
    id: str
    timestamp: datetime
    user_id: Optional[int]
    action: AuditEventType
    resource_type: Optional[str]
    resource_id: Optional[int]
    ip_address: Optional[str]
    user_agent: Optional[str]
    details: Dict[str, Any]
    risk_level: RiskLevel
    status: str  # success, failure, warning
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action.value,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": self.details,
            "risk_level": self.risk_level.value,
            "status": self.status,
            "session_id": self.session_id,
        }
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AuditLogStorage:
    """
    Audit log storage backend.
    
    Supports in-memory and file-based storage.
    """
    
    def __init__(
        self,
        storage_type: str = "memory",
        file_path: str = "logs/audit.log",
        max_entries: int = 100000,
        retention_days: int = 90
    ):
        self.storage_type = storage_type
        self.file_path = file_path
        self.max_entries = max_entries
        self.retention_days = retention_days
        
        # In-memory storage
        self._entries: deque[AuditLogEntry] = deque(maxlen=max_entries)
        
        # Indexes for fast lookup
        self._user_index: Dict[int, List[str]] = {}  # user_id -> [entry_ids]
        self._resource_index: Dict[str, Dict[int, List[str]]] = {}  # resource_type -> resource_id -> [entry_ids]
        self._action_index: Dict[str, List[str]] = {}  # action -> [entry_ids]
        
        logger.info(f"✅ Audit log storage initialized ({storage_type}, retention: {retention_days} days)")
    
    async def store(self, entry: AuditLogEntry) -> None:
        """Store audit log entry."""
        self._entries.append(entry)
        
        # Update indexes
        if entry.user_id:
            if entry.user_id not in self._user_index:
                self._user_index[entry.user_id] = []
            self._user_index[entry.user_id].append(entry.id)
        
        if entry.resource_type:
            if entry.resource_type not in self._resource_index:
                self._resource_index[entry.resource_type] = {}
            if entry.resource_id not in self._resource_index[entry.resource_type]:
                self._resource_index[entry.resource_type][entry.resource_id] = []
            self._resource_index[entry.resource_type][entry.resource_id].append(entry.id)
        
        if entry.action.value not in self._action_index:
            self._action_index[entry.action.value] = []
        self._action_index[entry.action.value].append(entry.id)
        
        # Write to file if configured
        if self.storage_type == "file":
            await self._write_to_file(entry)
    
    async def get_entries(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        risk_level: Optional[RiskLevel] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditLogEntry]:
        """Query audit log entries."""
        results = []
        
        for entry in self._entries:
            # Apply filters
            if user_id is not None and entry.user_id != user_id:
                continue
            if action is not None and entry.action.value != action:
                continue
            if resource_type is not None and entry.resource_type != resource_type:
                continue
            if resource_id is not None and entry.resource_id != resource_id:
                continue
            if start_date is not None and entry.timestamp < start_date:
                continue
            if end_date is not None and entry.timestamp > end_date:
                continue
            if risk_level is not None and entry.risk_level != risk_level:
                continue
            
            results.append(entry)
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Apply pagination
        return results[offset:offset + limit]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        now = datetime.utcnow()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        
        return {
            "total_entries": len(self._entries),
            "entries_last_24h": sum(1 for e in self._entries if e.timestamp > last_24h),
            "entries_last_7d": sum(1 for e in self._entries if e.timestamp > last_7d),
            "unique_users": len(self._user_index),
            "by_risk_level": {
                level.value: sum(1 for e in self._entries if e.risk_level == level)
                for level in RiskLevel
            },
            "by_action": {
                action: len(ids) for action, ids in self._action_index.items()
            }
        }
    
    async def cleanup_old_entries(self) -> int:
        """Remove entries older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        
        initial_count = len(self._entries)
        self._entries = deque(
            [e for e in self._entries if e.timestamp > cutoff],
            maxlen=self.max_entries
        )
        removed_count = initial_count - len(self._entries)
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old audit log entries")
        
        return removed_count
    
    async def _write_to_file(self, entry: AuditLogEntry) -> None:
        """Write entry to file."""
        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log to file: {e}")


class AuditLogger:
    """
    Main audit logger class.
    """
    
    def __init__(
        self,
        storage: Optional[AuditLogStorage] = None,
        async_write: bool = True
    ):
        self.storage = storage or AuditLogStorage()
        self.async_write = async_write
        self._entry_count = 0
        self._write_queue: asyncio.Queue = asyncio.Queue()
        self._write_task: Optional[asyncio.Task] = None
        
        # Risk level mapping
        self._risk_mapping = self._init_risk_mapping()
        
        logger.info("✅ Audit logger initialized")
    
    def _init_risk_mapping(self) -> Dict[AuditEventType, RiskLevel]:
        """Initialize risk level mapping for actions."""
        return {
            # Low risk
            AuditEventType.AUTH_LOGIN: RiskLevel.LOW,
            AuditEventType.AUTH_LOGOUT: RiskLevel.LOW,
            AuditEventType.PROPERTY_VIEWED: RiskLevel.LOW,
            
            # Medium risk
            AuditEventType.USER_UPDATED: RiskLevel.MEDIUM,
            AuditEventType.PROPERTY_CREATED: RiskLevel.MEDIUM,
            AuditEventType.PROPERTY_UPDATED: RiskLevel.MEDIUM,
            AuditEventType.API_KEY_USED: RiskLevel.MEDIUM,
            
            # High risk
            AuditEventType.AUTH_FAILED: RiskLevel.HIGH,
            AuditEventType.USER_PASSWORD_CHANGED: RiskLevel.HIGH,
            AuditEventType.API_KEY_CREATED: RiskLevel.HIGH,
            AuditEventType.API_KEY_REVOKED: RiskLevel.HIGH,
            AuditEventType.PERMISSION_CHANGED: RiskLevel.HIGH,
            
            # Critical
            AuditEventType.USER_DELETED: RiskLevel.CRITICAL,
            AuditEventType.PROPERTY_DELETED: RiskLevel.CRITICAL,
            AuditEventType.SECURITY_ALERT: RiskLevel.CRITICAL,
        }
    
    async def start(self) -> None:
        """Start async write processor."""
        if self.async_write:
            self._write_task = asyncio.create_task(self._process_write_queue())
            logger.info("✅ Audit log async writer started")
    
    async def stop(self) -> None:
        """Stop async write processor."""
        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except asyncio.CancelledError:
                pass
            logger.info("✅ Audit log async writer stopped")
    
    async def log_action(
        self,
        action: AuditEventType,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditLogEntry:
        """
        Log an audit event.
        
        Args:
            action: Type of action
            user_id: User ID who performed the action
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            ip_address: IP address of the request
            user_agent: User agent string
            details: Additional details about the action
            status: Status of the action (success, failure, warning)
            session_id: Session identifier
            metadata: Additional metadata
        
        Returns:
            Created audit log entry
        """
        # Generate entry ID
        timestamp = datetime.utcnow()
        entry_id = self._generate_entry_id(timestamp, user_id, action)
        
        # Determine risk level
        risk_level = self._risk_mapping.get(action, RiskLevel.MEDIUM)
        
        # Create entry
        entry = AuditLogEntry(
            id=entry_id,
            timestamp=timestamp,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            risk_level=risk_level,
            status=status,
            session_id=session_id,
            metadata=metadata or {}
        )
        
        # Store entry
        if self.async_write:
            await self._write_queue.put(entry)
        else:
            await self.storage.store(entry)
        
        # Log to standard logger for critical events
        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            log_msg = f"Audit: {action.value} by user {user_id}"
            if risk_level == RiskLevel.CRITICAL:
                logger.critical(log_msg, extra={"audit": entry.to_dict()})
            else:
                logger.warning(log_msg, extra={"audit": entry.to_dict()})
        
        self._entry_count += 1
        return entry
    
    async def get_audit_trail(
        self,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLogEntry]:
        """Get audit trail for a user or system."""
        return await self.storage.get_entries(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        stats = await self.storage.get_stats()
        stats["entry_count"] = self._entry_count
        return stats
    
    async def _process_write_queue(self) -> None:
        """Process async write queue."""
        batch = []
        batch_size = 10
        flush_interval = 5.0  # seconds
        
        last_flush = time.time()
        
        while True:
            try:
                # Get entry with timeout
                try:
                    entry = await asyncio.wait_for(
                        self._write_queue.get(),
                        timeout=1.0
                    )
                    batch.append(entry)
                except asyncio.TimeoutError:
                    pass
                
                # Flush batch if full or timeout
                now = time.time()
                if len(batch) >= batch_size or (batch and now - last_flush > flush_interval):
                    for entry in batch:
                        await self.storage.store(entry)
                    batch = []
                    last_flush = now
                    
            except asyncio.CancelledError:
                # Flush remaining entries
                for entry in batch:
                    await self.storage.store(entry)
                break
            except Exception as e:
                logger.error(f"Audit log write error: {e}")
    
    def _generate_entry_id(self, timestamp: datetime, user_id: Optional[int], action: AuditEventType) -> str:
        """Generate unique entry ID."""
        data = f"{timestamp.isoformat()}-{user_id}-{action.value}-{time.time_ns()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


# Global audit logger instance
audit_logger = AuditLogger(
    storage=AuditLogStorage(
        storage_type="file",
        file_path="logs/audit.log"
    )
)


__all__ = [
    "AuditLogger",
    "AuditLogStorage",
    "AuditLogEntry",
    "AuditEventType",
    "RiskLevel",
    "audit_logger",
]
