"""
Tests for PostgreSQL alerts repository.
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import alerts as alerts_repo


@pytest.fixture
def sample_alert_data():
    """Sample alert data for testing."""
    return {
        "city": "Moscow",
        "max_price": 100000.0,
        "min_price": 50000.0,
        "rooms": 2,
        "min_area": 50.0,
        "max_area": 80.0,
        "email": "test@example.com"
    }


@pytest.mark.asyncio
async def test_create_alert(db_session: AsyncSession, sample_alert_data):
    """Test creating a property alert."""
    # Create alert
    alert = await alerts_repo.create_alert(db_session, sample_alert_data)
    
    # Verify alert was created
    assert alert.id is not None
    assert alert.city == sample_alert_data["city"]
    assert alert.email == sample_alert_data["email"]
    assert alert.is_active is True


@pytest.mark.asyncio
async def test_get_alert(db_session: AsyncSession, sample_alert_data):
    """Test getting a property alert by ID."""
    # Create alert
    created_alert = await alerts_repo.create_alert(db_session, sample_alert_data)
    
    # Get alert
    fetched_alert = await alerts_repo.get_alert(db_session, created_alert.id)
    
    # Verify alert was fetched correctly
    assert fetched_alert is not None
    assert fetched_alert.id == created_alert.id
    assert fetched_alert.city == sample_alert_data["city"]


@pytest.mark.asyncio
async def test_get_alerts_by_email(db_session: AsyncSession, sample_alert_data):
    """Test getting property alerts by email."""
    # Create alert
    await alerts_repo.create_alert(db_session, sample_alert_data)
    
    # Get alerts by email
    alerts = await alerts_repo.get_alerts_by_email(db_session, sample_alert_data["email"])
    
    # Verify alerts were fetched correctly
    assert len(alerts) > 0
    assert alerts[0].email == sample_alert_data["email"]


@pytest.mark.asyncio
async def test_update_alert(db_session: AsyncSession, sample_alert_data):
    """Test updating a property alert."""
    # Create alert
    created_alert = await alerts_repo.create_alert(db_session, sample_alert_data)
    
    # Update alert
    update_data = {"max_price": 120000.0, "rooms": 3}
    updated_alert = await alerts_repo.update_alert(db_session, created_alert.id, update_data)
    
    # Verify alert was updated
    assert updated_alert is not None
    assert updated_alert.max_price == 120000.0
    assert updated_alert.rooms == 3


@pytest.mark.asyncio
async def test_deactivate_alert(db_session: AsyncSession, sample_alert_data):
    """Test deactivating a property alert."""
    # Create alert
    created_alert = await alerts_repo.create_alert(db_session, sample_alert_data)
    
    # Deactivate alert
    success = await alerts_repo.deactivate_alert(db_session, created_alert.id)
    
    # Verify alert was deactivated
    assert success is True
    
    # Fetch the alert again to verify it's inactive
    fetched_alert = await alerts_repo.get_alert(db_session, created_alert.id)
    assert fetched_alert is not None
    assert fetched_alert.is_active is False


@pytest.mark.asyncio
async def test_delete_alert(db_session: AsyncSession, sample_alert_data):
    """Test deleting a property alert."""
    # Create alert
    created_alert = await alerts_repo.create_alert(db_session, sample_alert_data)
    
    # Delete alert
    success = await alerts_repo.delete_alert(db_session, created_alert.id)
    
    # Verify alert was deleted
    assert success is True
    
    # Try to fetch the deleted alert
    fetched_alert = await alerts_repo.get_alert(db_session, created_alert.id)
    assert fetched_alert is None


@pytest.mark.asyncio
async def test_get_active_alerts(db_session: AsyncSession, sample_alert_data):
    """Test getting all active property alerts."""
    # Create alert
    await alerts_repo.create_alert(db_session, sample_alert_data)
    
    # Get active alerts
    alerts = await alerts_repo.get_active_alerts(db_session)
    
    # Verify active alerts were fetched
    assert len(alerts) > 0
    for alert in alerts:
        assert alert.is_active is True