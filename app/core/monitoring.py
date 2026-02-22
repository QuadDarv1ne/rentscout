"""
Enhanced Monitoring & Alerting System for RentScout.

Features:
- System health monitoring
- Performance metrics tracking
- Automated alerting (email, webhook, Telegram)
- Alert rules engine
- Incident tracking

Usage:
    from app.core.monitoring import MonitoringSystem
    
    monitoring = MonitoringSystem()
    
    # Add alert rule
    monitoring.add_rule(
        name="high_error_rate",
        metric="error_rate",
        threshold=0.05,
        alert_channels=["email", "telegram"]
    )
    
    # Check metrics
    await monitoring.check_alerts()
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import json
import hashlib

from app.utils.logger import logger


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertChannel(str, Enum):
    """Alert notification channels."""
    EMAIL = "email"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    SLACK = "slack"
    PAGERDUTY = "pagerduty"


@dataclass
class AlertRule:
    """Alert rule definition."""
    name: str
    metric: str
    threshold: float
    operator: str  # gt, lt, eq, gte, lte
    severity: AlertSeverity
    channels: List[AlertChannel]
    cooldown_seconds: int = 300
    enabled: bool = True
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0


@dataclass
class Alert:
    """Alert instance."""
    id: str
    rule_name: str
    metric_name: str
    current_value: float
    threshold: float
    severity: AlertSeverity
    status: AlertStatus
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "message": self.message,
        }


@dataclass
class MetricPoint:
    """Single metric data point."""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Metrics collector for system monitoring.
    """
    
    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self._metrics: Dict[str, List[MetricPoint]] = {}
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
    
    def increment(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment counter."""
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set gauge value."""
        key = self._make_key(name, labels)
        self._gauges[key] = value
        
        # Also store as time series
        self._store_metric(name, value, labels)
    
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Observe histogram value."""
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        
        # Keep last 1000 values
        if len(self._histograms[key]) > 1000:
            self._histograms[key] = self._histograms[key][-1000:]
    
    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get counter value."""
        key = self._make_key(name, labels)
        return self._counters.get(key, 0)
    
    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value."""
        key = self._make_key(name, labels)
        return self._gauges.get(key)
    
    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._make_key(name, labels)
        values = self._histograms.get(key, [])
        
        if not values:
            return {"count": 0, "avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0, "p99": 0}
        
        sorted_values = sorted(values)
        count = len(sorted_values)
        
        return {
            "count": count,
            "avg": sum(values) / count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p50": sorted_values[int(count * 0.5)],
            "p95": sorted_values[int(count * 0.95)] if count > 20 else sorted_values[-1],
            "p99": sorted_values[int(count * 0.99)] if count > 100 else sorted_values[-1],
        }
    
    def get_metric_history(self, name: str, hours: int = 1) -> List[Dict[str, Any]]:
        """Get metric history."""
        points = self._metrics.get(name, [])
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        return [
            {
                "value": p.value,
                "timestamp": p.timestamp.isoformat(),
                "labels": p.labels
            }
            for p in points
            if p.timestamp > cutoff
        ]
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create metric key with labels."""
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def _store_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Store metric in time series."""
        if name not in self._metrics:
            self._metrics[name] = []
        
        point = MetricPoint(
            name=name,
            value=value,
            timestamp=datetime.utcnow(),
            labels=labels or {}
        )
        self._metrics[name].append(point)
        
        # Cleanup old data
        cutoff = datetime.utcnow() - timedelta(hours=self.retention_hours)
        self._metrics[name] = [p for p in self._metrics[name] if p.timestamp > cutoff]
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: self.get_histogram_stats(k.split("{")[0] if "{" in k else k)
                for k in self._histograms
            }
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._metrics.clear()


class AlertManager:
    """
    Alert manager for monitoring system.
    """
    
    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._alerts: Dict[str, Alert] = {}
        self._notification_handlers: Dict[AlertChannel, Callable] = {}
        self._alert_count = 0
    
    def add_rule(
        self,
        name: str,
        metric: str,
        threshold: float,
        operator: str = "gt",
        severity: AlertSeverity = AlertSeverity.WARNING,
        channels: Optional[List[AlertChannel]] = None,
        cooldown_seconds: int = 300
    ) -> None:
        """Add alert rule."""
        self._rules[name] = AlertRule(
            name=name,
            metric=metric,
            threshold=threshold,
            operator=operator,
            severity=severity,
            channels=channels or [AlertChannel.EMAIL],
            cooldown_seconds=cooldown_seconds
        )
        logger.info(f"Added alert rule: {name}")
    
    def remove_rule(self, name: str) -> bool:
        """Remove alert rule."""
        if name in self._rules:
            del self._rules[name]
            return True
        return False
    
    def register_notification_handler(
        self,
        channel: AlertChannel,
        handler: Callable[[Alert], Awaitable[None]]
    ) -> None:
        """Register notification handler for channel."""
        self._notification_handlers[channel] = handler
    
    async def check_alerts(self, metrics: Dict[str, float]) -> List[Alert]:
        """Check all alert rules against current metrics."""
        triggered_alerts = []
        now = datetime.utcnow()
        
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            
            # Get metric value
            metric_value = metrics.get(rule.metric)
            if metric_value is None:
                continue
            
            # Check if rule triggered
            triggered = self._evaluate_rule(rule, metric_value)
            
            if triggered:
                # Check cooldown
                if rule.last_triggered:
                    cooldown_end = rule.last_triggered + timedelta(seconds=rule.cooldown_seconds)
                    if now < cooldown_end:
                        continue
                
                # Create alert
                alert = self._create_alert(rule, metric_value)
                self._alerts[alert.id] = alert
                triggered_alerts.append(alert)
                
                # Update rule
                rule.last_triggered = now
                rule.trigger_count += 1
                
                # Send notifications
                await self._send_notifications(alert)
        
        return triggered_alerts
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge alert."""
        alert = self._alerts.get(alert_id)
        if not alert or alert.status != AlertStatus.ACTIVE:
            return False
        
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        logger.info(f"Acknowledged alert: {alert_id}")
        return True
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return False
        
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        logger.info(f"Resolved alert: {alert_id}")
        return True
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        return [
            a for a in self._alerts.values()
            if a.status == AlertStatus.ACTIVE
        ]
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        now = datetime.utcnow()
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)
        
        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "total_alerts": len(self._alerts),
            "active_alerts": sum(1 for a in self._alerts.values() if a.status == AlertStatus.ACTIVE),
            "alerts_last_hour": sum(
                1 for a in self._alerts.values()
                if a.created_at > last_hour
            ),
            "alerts_last_day": sum(
                1 for a in self._alerts.values()
                if a.created_at > last_day
            ),
            "by_severity": {
                severity.value: sum(
                    1 for a in self._alerts.values()
                    if a.severity == severity and a.status == AlertStatus.ACTIVE
                )
                for severity in AlertSeverity
            }
        }
    
    def _evaluate_rule(self, rule: AlertRule, value: float) -> bool:
        """Evaluate if rule should trigger."""
        ops = {
            "gt": lambda v, t: v > t,
            "lt": lambda v, t: v < t,
            "eq": lambda v, t: v == t,
            "gte": lambda v, t: v >= t,
            "lte": lambda v, t: v <= t,
        }
        
        op_func = ops.get(rule.operator)
        if not op_func:
            return False
        
        return op_func(value, rule.threshold)
    
    def _create_alert(self, rule: AlertRule, value: float) -> Alert:
        """Create new alert."""
        self._alert_count += 1
        alert_id = f"alert_{int(time.time())}_{self._alert_count}"
        
        message = f"Alert: {rule.name} - {rule.metric} is {rule.operator} {rule.threshold} (current: {value})"
        
        return Alert(
            id=alert_id,
            rule_name=rule.name,
            metric_name=rule.metric,
            current_value=value,
            threshold=rule.threshold,
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            created_at=datetime.utcnow(),
            message=message
        )
    
    async def _send_notifications(self, alert: Alert) -> None:
        """Send notifications for alert."""
        for channel in self._rules[alert.rule_name].channels:
            handler = self._notification_handlers.get(channel)
            if handler:
                try:
                    await handler(alert)
                except Exception as e:
                    logger.error(f"Failed to send {channel.value} notification: {e}")
    
    def list_rules(self) -> List[Dict[str, Any]]:
        """List all alert rules."""
        return [
            {
                "name": r.name,
                "metric": r.metric,
                "threshold": r.threshold,
                "operator": r.operator,
                "severity": r.severity.value,
                "enabled": r.enabled,
                "trigger_count": r.trigger_count,
            }
            for r in self._rules.values()
        ]


class MonitoringSystem:
    """
    Main monitoring system combining metrics and alerting.
    """
    
    def __init__(self):
        self.metrics = MetricsCollector()
        self.alerts = AlertManager()
        self._system_checks: Dict[str, Callable[[], Awaitable[bool]]] = {}
        self._running = False
        self._check_task: Optional[asyncio.Task] = None
        
        logger.info("✅ Monitoring system initialized")
    
    def register_system_check(self, name: str, check: Callable[[], Awaitable[bool]]) -> None:
        """Register system health check."""
        self._system_checks[name] = check
    
    async def start(self, check_interval_seconds: int = 60) -> None:
        """Start monitoring loop."""
        self._running = True
        
        async def monitor_loop():
            while self._running:
                await self._run_checks()
                await asyncio.sleep(check_interval_seconds)
        
        self._check_task = asyncio.create_task(monitor_loop())
        logger.info(f"✅ Monitoring started (interval: {check_interval_seconds}s)")
    
    async def stop(self) -> None:
        """Stop monitoring loop."""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass
        logger.info("✅ Monitoring stopped")
    
    async def _run_checks(self) -> None:
        """Run all monitoring checks."""
        try:
            # Collect system metrics
            await self._collect_system_metrics()
            
            # Check alerts
            metrics = self.metrics.get_all_metrics()
            flat_metrics = self._flatten_metrics(metrics)
            await self.alerts.check_alerts(flat_metrics)
            
        except Exception as e:
            logger.error(f"Monitoring check failed: {e}")
    
    async def _collect_system_metrics(self) -> None:
        """Collect system metrics."""
        # Run system checks
        for name, check in self._system_checks.items():
            try:
                start = time.time()
                result = await check()
                duration = time.time() - start
                
                self.metrics.set_gauge(f"system_check_result", 1 if result else 0, {"check": name})
                self.metrics.set_gauge(f"system_check_duration", duration, {"check": name})
            except Exception as e:
                logger.error(f"System check {name} failed: {e}")
                self.metrics.set_gauge(f"system_check_result", 0, {"check": name})
    
    def _flatten_metrics(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        """Flatten metrics dict for alert evaluation."""
        flat = {}
        
        # Gauges
        for key, value in metrics.get("gauges", {}).items():
            flat[key] = value
        
        # Histogram stats
        for key, stats in metrics.get("histograms", {}).items():
            flat[f"{key}_avg"] = stats.get("avg", 0)
            flat[f"{key}_p95"] = stats.get("p95", 0)
            flat[f"{key}_p99"] = stats.get("p99", 0)
        
        return flat
    
    def get_status(self) -> Dict[str, Any]:
        """Get monitoring system status."""
        return {
            "running": self._running,
            "metrics": self.metrics.get_all_metrics(),
            "alerts": self.alerts.get_alert_stats(),
            "system_checks": list(self._system_checks.keys()),
        }


# Global monitoring system instance
monitoring_system = MonitoringSystem()


__all__ = [
    "MonitoringSystem",
    "MetricsCollector",
    "AlertManager",
    "AlertRule",
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "AlertChannel",
    "monitoring_system",
]
