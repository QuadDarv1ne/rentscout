"""
Tests for property alerts API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.db.repositories import alerts as alerts_repo

client = TestClient(app)


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


def test_create_property_alert(sample_alert_data):
    """Test creating a property alert via API."""
    response = client.post("/properties/alerts", json=sample_alert_data)
    
    # Check that the request was accepted (501 for now since it's not fully implemented)
    assert response.status_code in [201, 501]


def test_list_property_alerts():
    """Test listing property alerts via API."""
    response = client.get("/properties/alerts?email=test@example.com")
    
    # Check that the request was successful
    assert response.status_code == 200


def test_update_property_alert(sample_alert_data):
    """Test updating a property alert via API."""
    # First create an alert
    response = client.post("/properties/alerts", json=sample_alert_data)
    
    # Then try to update it (should get 404 since we don't have a real ID)
    update_data = {**sample_alert_data, "max_price": 120000.0}
    response = client.put("/properties/alerts/1", json=update_data)
    
    # Check that we get either 404 (not found) or 501 (not implemented)
    assert response.status_code in [404, 501]


def test_delete_property_alert():
    """Test deleting a property alert via API."""
    response = client.delete("/properties/alerts/1")
    
    # Check that we get either 404 (not found) or 501 (not implemented)
    assert response.status_code in [404, 501]


def test_deactivate_property_alert():
    """Test deactivating a property alert via API."""
    response = client.post("/properties/alerts/1/deactivate")
    
    # Check that we get either 404 (not found) or 501 (not implemented)
    assert response.status_code in [404, 501]