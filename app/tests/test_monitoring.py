"""
Tests for enhanced monitoring & alerting.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.core.monitoring import (
    MonitoringSystem,
    MetricsCollector,
    AlertManager,
    AlertRule,
    Alert,
    AlertSeverity,
    AlertStatus,
    AlertChannel,
    monitoring_system,
)


class TestAlertSeverity:
    """Tests for AlertSeverity enum."""

    def test_severity_values(self):
        """Test severity values."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"


class TestAlertStatus:
    """Tests for AlertStatus enum."""

    def test_status_values(self):
        """Test status values."""
        assert AlertStatus.ACTIVE.value == "active"
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlertStatus.RESOLVED.value == "resolved"


class TestAlertChannel:
    """Tests for AlertChannel enum."""

    def test_channel_values(self):
        """Test channel values."""
        assert AlertChannel.EMAIL.value == "email"
        assert AlertChannel.TELEGRAM.value == "telegram"
        assert AlertChannel.WEBHOOK.value == "webhook"


class TestAlert:
    """Tests for Alert dataclass."""

    def test_create_alert(self):
        """Test creating alert."""
        alert = Alert(
            id="test_1",
            rule_name="high_cpu",
            metric_name="cpu_usage",
            current_value=95.0,
            threshold=90.0,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            created_at=datetime.utcnow(),
            message="CPU usage is high"
        )
        assert alert.id == "test_1"
        assert alert.current_value == 95.0
        assert alert.severity == AlertSeverity.WARNING

    def test_alert_to_dict(self):
        """Test alert to_dict."""
        alert = Alert(
            id="test_1",
            rule_name="high_cpu",
            metric_name="cpu_usage",
            current_value=95.0,
            threshold=90.0,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            created_at=datetime.utcnow(),
        )
        data = alert.to_dict()
        assert "id" in data
        assert "rule_name" in data
        assert data["current_value"] == 95.0
        assert data["severity"] == "warning"


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_increment_counter(self):
        """Test counter increment."""
        collector = MetricsCollector()
        collector.increment("requests")
        collector.increment("requests", 5)
        
        assert collector.get_counter("requests") == 6

    def test_increment_counter_with_labels(self):
        """Test counter with labels."""
        collector = MetricsCollector()
        collector.increment("requests", labels={"method": "GET"})
        collector.increment("requests", labels={"method": "POST"})
        
        assert collector.get_counter("requests", {"method": "GET"}) == 1
        assert collector.get_counter("requests", {"method": "POST"}) == 1

    def test_set_gauge(self):
        """Test gauge set."""
        collector = MetricsCollector()
        collector.set_gauge("temperature", 25.5)
        
        assert collector.get_gauge("temperature") == 25.5
        
        # Update value
        collector.set_gauge("temperature", 30.0)
        assert collector.get_gauge("temperature") == 30.0

    def test_observe_histogram(self):
        """Test histogram observation."""
        collector = MetricsCollector()
        for i in range(100):
            collector.observe_histogram("response_time", i)
        
        stats = collector.get_histogram_stats("response_time")
        assert stats["count"] == 100
        assert stats["min"] == 0
        assert stats["max"] == 99
        assert stats["avg"] == 49.5

    def test_get_metric_history(self):
        """Test metric history."""
        collector = MetricsCollector()
        collector.set_gauge("cpu", 50)
        
        history = collector.get_metric_history("cpu", hours=1)
        assert len(history) >= 1
        assert history[0]["value"] == 50

    def test_get_all_metrics(self):
        """Test getting all metrics."""
        collector = MetricsCollector()
        collector.increment("requests")
        collector.set_gauge("cpu", 50)
        collector.observe_histogram("latency", 100)
        
        metrics = collector.get_all_metrics()
        assert "counters" in metrics
        assert "gauges" in metrics
        assert "histograms" in metrics

    def test_reset_metrics(self):
        """Test reset."""
        collector = MetricsCollector()
        collector.increment("requests")
        collector.set_gauge("cpu", 50)
        collector.reset()
        
        metrics = collector.get_all_metrics()
        assert len(metrics["counters"]) == 0
        assert len(metrics["gauges"]) == 0


class TestAlertManager:
    """Tests for AlertManager."""

    def test_add_rule(self):
        """Test adding alert rule."""
        manager = AlertManager()
        manager.add_rule(
            name="high_cpu",
            metric="cpu_usage",
            threshold=90,
            operator="gt",
            severity=AlertSeverity.WARNING
        )
        
        assert "high_cpu" in manager._rules
        assert manager._rules["high_cpu"].threshold == 90

    def test_remove_rule(self):
        """Test removing rule."""
        manager = AlertManager()
        manager.add_rule("test", "metric", 100)
        
        result = manager.remove_rule("test")
        assert result is True
        assert "test" not in manager._rules

    def test_remove_nonexistent_rule(self):
        """Test removing nonexistent rule."""
        manager = AlertManager()
        result = manager.remove_rule("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_check_alerts_triggered(self):
        """Test alert triggering."""
        manager = AlertManager()
        manager.add_rule(
            name="high_cpu",
            metric="cpu_usage",
            threshold=90,
            operator="gt",
            severity=AlertSeverity.WARNING
        )
        
        metrics = {"cpu_usage": 95}
        alerts = await manager.check_alerts(metrics)
        
        assert len(alerts) == 1
        assert alerts[0].rule_name == "high_cpu"
        assert alerts[0].current_value == 95

    @pytest.mark.asyncio
    async def test_check_alerts_not_triggered(self):
        """Test alert not triggering."""
        manager = AlertManager()
        manager.add_rule(
            name="high_cpu",
            metric="cpu_usage",
            threshold=90,
            operator="gt"
        )
        
        metrics = {"cpu_usage": 80}
        alerts = await manager.check_alerts(metrics)
        
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_cooldown(self):
        """Test alert cooldown."""
        manager = AlertManager()
        manager.add_rule(
            name="high_cpu",
            metric="cpu_usage",
            threshold=90,
            operator="gt",
            cooldown_seconds=60
        )
        
        # First trigger
        metrics = {"cpu_usage": 95}
        alerts = await manager.check_alerts(metrics)
        assert len(alerts) == 1
        
        # Second trigger (should be on cooldown)
        alerts = await manager.check_alerts(metrics)
        assert len(alerts) == 0

    def test_acknowledge_alert(self):
        """Test acknowledging alert."""
        manager = AlertManager()
        alert = Alert(
            id="test_1",
            rule_name="test",
            metric_name="test",
            current_value=100,
            threshold=90,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            created_at=datetime.utcnow()
        )
        manager._alerts["test_1"] = alert
        
        result = manager.acknowledge_alert("test_1")
        assert result is True
        assert alert.status == AlertStatus.ACKNOWLEDGED

    def test_acknowledge_nonexistent_alert(self):
        """Test acknowledging nonexistent alert."""
        manager = AlertManager()
        result = manager.acknowledge_alert("nonexistent")
        assert result is False

    def test_resolve_alert(self):
        """Test resolving alert."""
        manager = AlertManager()
        alert = Alert(
            id="test_1",
            rule_name="test",
            metric_name="test",
            current_value=100,
            threshold=90,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            created_at=datetime.utcnow()
        )
        manager._alerts["test_1"] = alert
        
        result = manager.resolve_alert("test_1")
        assert result is True
        assert alert.status == AlertStatus.RESOLVED

    def test_get_active_alerts(self):
        """Test getting active alerts."""
        manager = AlertManager()
        
        alert1 = Alert(
            id="test_1", rule_name="test", metric_name="test",
            current_value=100, threshold=90,
            severity=AlertSeverity.WARNING, status=AlertStatus.ACTIVE,
            created_at=datetime.utcnow()
        )
        alert2 = Alert(
            id="test_2", rule_name="test", metric_name="test",
            current_value=100, threshold=90,
            severity=AlertSeverity.WARNING, status=AlertStatus.RESOLVED,
            created_at=datetime.utcnow()
        )
        manager._alerts["test_1"] = alert1
        manager._alerts["test_2"] = alert2
        
        active = manager.get_active_alerts()
        assert len(active) == 1
        assert active[0].id == "test_1"

    def test_get_alert_stats(self):
        """Test alert statistics."""
        manager = AlertManager()
        manager.add_rule("test", "metric", 100)
        
        stats = manager.get_alert_stats()
        assert "total_rules" in stats
        assert "active_alerts" in stats
        assert "by_severity" in stats

    def test_list_rules(self):
        """Test listing rules."""
        manager = AlertManager()
        manager.add_rule("test", "metric", 100, severity=AlertSeverity.ERROR)
        
        rules = manager.list_rules()
        assert len(rules) == 1
        assert rules[0]["name"] == "test"
        assert rules[0]["severity"] == "error"


class TestMonitoringSystem:
    """Tests for MonitoringSystem."""

    def test_init(self):
        """Test initialization."""
        monitoring = MonitoringSystem()
        assert monitoring.metrics is not None
        assert monitoring.alerts is not None
        assert monitoring._running is False

    def test_register_system_check(self):
        """Test registering system check."""
        monitoring = MonitoringSystem()
        
        async def check():
            return True
        
        monitoring.register_system_check("test_check", check)
        assert "test_check" in monitoring._system_checks

    def test_get_status(self):
        """Test getting status."""
        monitoring = MonitoringSystem()
        status = monitoring.get_status()
        
        assert "running" in status
        assert "metrics" in status
        assert "alerts" in status

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test start/stop monitoring."""
        monitoring = MonitoringSystem()
        
        await monitoring.start(check_interval_seconds=1)
        assert monitoring._running is True
        
        await asyncio.sleep(0.1)
        
        await monitoring.stop()
        assert monitoring._running is False

    @pytest.mark.asyncio
    async def test_run_checks(self):
        """Test running checks."""
        monitoring = MonitoringSystem()
        
        check_called = False
        
        async def test_check():
            nonlocal check_called
            check_called = True
            return True
        
        monitoring.register_system_check("test", test_check)
        await monitoring._run_checks()
        
        assert check_called is True


class TestGlobalMonitoringSystem:
    """Tests for global monitoring system."""

    def test_global_instance_exists(self):
        """Test global instance exists."""
        assert monitoring_system is not None
        assert isinstance(monitoring_system, MonitoringSystem)


class TestMonitoringIntegration:
    """Integration tests for monitoring."""

    @pytest.mark.asyncio
    async def test_full_monitoring_workflow(self):
        """Test complete monitoring workflow."""
        monitoring = MonitoringSystem()
        
        # Add alert rule
        monitoring.alerts.add_rule(
            name="high_error_rate",
            metric="error_rate",
            threshold=0.05,
            operator="gt",
            severity=AlertSeverity.ERROR
        )
        
        # Record metrics
        monitoring.metrics.set_gauge("error_rate", 0.1)
        
        # Check alerts
        metrics = {"error_rate": 0.1}
        alerts = await monitoring.alerts.check_alerts(metrics)
        
        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.ERROR
        
        # Get status
        status = monitoring.get_status()
        assert status["running"] is False
        assert "error_rate" in str(status["metrics"])

    @pytest.mark.asyncio
    async def test_metric_collection_workflow(self):
        """Test metric collection workflow."""
        collector = MetricsCollector()
        
        # Record various metrics
        collector.increment("http_requests", labels={"status": "200"})
        collector.increment("http_requests", labels={"status": "500"})
        collector.set_gauge("active_connections", 150)
        
        for i in range(50):
            collector.observe_histogram("response_time_ms", i * 10)
        
        # Get metrics
        all_metrics = collector.get_all_metrics()
        
        assert all_metrics["counters"]["http_requests{status=200}"] == 1
        assert all_metrics["counters"]["http_requests{status=500}"] == 1
        assert all_metrics["gauges"]["active_connections"] == 150
        assert all_metrics["histograms"]["response_time_ms"]["count"] == 50
