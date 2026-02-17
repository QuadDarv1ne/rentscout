"""
Tests for Database Connection Pool Monitoring
"""

import pytest
from unittest.mock import patch, MagicMock
from app.utils.db_pool_monitor import DatabasePoolMonitor, get_db_pool_health


@pytest.fixture
def db_pool_monitor():
    """Create a fresh DatabasePoolMonitor instance for testing."""
    return DatabasePoolMonitor()


def test_db_pool_monitor_initialization(db_pool_monitor):
    """Test that DatabasePoolMonitor initializes correctly."""
    assert db_pool_monitor.checkout_count == 0
    assert db_pool_monitor.checkin_count == 0
    assert db_pool_monitor.connect_count == 0
    assert db_pool_monitor.disconnect_count == 0
    assert db_pool_monitor.connection_errors == 0
    assert isinstance(db_pool_monitor.checkout_times, list)


def test_db_pool_monitor_get_stats_empty(db_pool_monitor):
    """Test get_pool_stats with no activity."""
    with patch('app.utils.db_pool_monitor.engine') as mock_engine:
        # Mock the pool
        mock_pool = MagicMock()
        mock_pool.size.return_value = 10
        mock_engine.pool = mock_pool
        
        stats = db_pool_monitor.get_pool_stats()
        
        assert stats["pool_size"] == 10
        assert stats["checked_out_connections"] == 0
        assert stats["total_checkouts"] == 0
        assert stats["total_checkins"] == 0
        assert stats["total_connections"] == 0
        assert stats["total_disconnections"] == 0
        assert stats["connection_errors"] == 0
        assert stats["average_checkout_time"] == 0.0
        assert stats["current_pool_utilization"] == 0.0


def test_db_pool_monitor_checkout_checkin(db_pool_monitor):
    """Test checkout and checkin counting."""
    # Simulate checkout
    db_pool_monitor.checkout_count = 5
    db_pool_monitor.checkin_count = 3
    
    with patch('app.utils.db_pool_monitor.engine') as mock_engine:
        mock_pool = MagicMock()
        mock_pool.size.return_value = 10
        mock_engine.pool = mock_pool
        
        stats = db_pool_monitor.get_pool_stats()
        
        assert stats["checked_out_connections"] == 2  # 5 - 3
        assert stats["current_pool_utilization"] == 20.0  # 2/10 * 100


def test_db_pool_monitor_reset_stats(db_pool_monitor):
    """Test reset_stats method."""
    # Set some values
    db_pool_monitor.checkout_count = 10
    db_pool_monitor.checkin_count = 5
    db_pool_monitor.connect_count = 3
    db_pool_monitor.disconnect_count = 2
    db_pool_monitor.connection_errors = 1
    db_pool_monitor.checkout_times = [1.0, 2.0, 3.0]
    
    # Reset stats
    db_pool_monitor.reset_stats()
    
    # Check that all values are reset
    assert db_pool_monitor.checkout_count == 0
    assert db_pool_monitor.checkin_count == 0
    assert db_pool_monitor.connect_count == 0
    assert db_pool_monitor.disconnect_count == 0
    assert db_pool_monitor.connection_errors == 0
    assert db_pool_monitor.checkout_times == []


def test_get_db_pool_health(db_pool_monitor):
    """Test get_db_pool_health function."""
    # Test healthy status
    db_pool_monitor.checkout_count = 2
    db_pool_monitor.checkin_count = 2
    health = get_db_pool_health()
    assert health["health_status"] == "healthy"
    assert len(health["recommendations"]) == 0
    
    # Test warning status
    db_pool_monitor.checkout_count = 9
    db_pool_monitor.checkin_count = 1
    health = get_db_pool_health()
    assert health["health_status"] == "warning"
    assert len(health["recommendations"]) > 0
    
    # Test critical status
    db_pool_monitor.checkout_count = 19
    db_pool_monitor.checkin_count = 1
    health = get_db_pool_health()
    assert health["health_status"] == "critical"
    assert len(health["recommendations"]) > 0