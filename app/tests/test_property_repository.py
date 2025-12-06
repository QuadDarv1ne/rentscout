"""
Tests for PostgreSQL property repository.
"""
import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import property as property_repo
from app.models.schemas import PropertyCreate


@pytest.fixture
def sample_property_data():
    """Sample property data for testing."""
    return PropertyCreate(
        source="test",
        external_id="test123",
        title="Test Property",
        description="Test description",
        link="https://example.com/test123",
        price=50000.0,
        rooms=2,
        area=60.0,
        location={
            "city": "Moscow",
            "district": "Center",
            "address": "Test Street 1",
            "latitude": 55.751244,
            "longitude": 37.618423
        },
        photos=["photo1.jpg", "photo2.jpg"]
    )


@pytest.mark.asyncio
async def test_create_property(db_session: AsyncSession, sample_property_data):
    """Test creating a new property."""
    property = await property_repo.create_property(db_session, sample_property_data)
    
    assert property.id is not None
    assert property.source == "test"
    assert property.external_id == "test123"
    assert property.title == "Test Property"
    assert property.price == 50000.0
    assert property.city == "Moscow"


@pytest.mark.asyncio
async def test_get_property(db_session: AsyncSession, sample_property_data):
    """Test getting a property by ID."""
    # Create property
    created = await property_repo.create_property(db_session, sample_property_data)
    
    # Retrieve it
    property = await property_repo.get_property(db_session, created.id)
    
    assert property is not None
    assert property.id == created.id
    assert property.external_id == "test123"


@pytest.mark.asyncio
async def test_get_property_by_external_id(db_session: AsyncSession, sample_property_data):
    """Test getting a property by source and external ID."""
    # Create property
    await property_repo.create_property(db_session, sample_property_data)
    
    # Retrieve by external ID
    property = await property_repo.get_property_by_external_id(
        db_session, "test", "test123"
    )
    
    assert property is not None
    assert property.source == "test"
    assert property.external_id == "test123"


@pytest.mark.asyncio
async def test_update_or_create_property_create(db_session: AsyncSession, sample_property_data):
    """Test update_or_create when property doesn't exist (create)."""
    property, created = await property_repo.update_or_create_property(
        db_session, sample_property_data
    )
    
    assert created is True
    assert property.external_id == "test123"


@pytest.mark.asyncio
async def test_update_or_create_property_update(db_session: AsyncSession, sample_property_data):
    """Test update_or_create when property exists (update)."""
    # Create initial property
    await property_repo.create_property(db_session, sample_property_data)
    
    # Update with new price
    updated_data = sample_property_data.model_copy(update={"price": 60000.0})
    property, created = await property_repo.update_or_create_property(
        db_session, updated_data
    )
    
    assert created is False
    assert property.price == 60000.0


@pytest.mark.asyncio
async def test_search_properties_by_city(db_session: AsyncSession):
    """Test searching properties by city."""
    # Create properties in different cities
    prop1 = PropertyCreate(
        source="test", external_id="test1", title="Moscow Property",
        price=50000.0, location={"city": "Moscow"}
    )
    prop2 = PropertyCreate(
        source="test", external_id="test2", title="SPb Property",
        price=60000.0, location={"city": "Saint Petersburg"}
    )
    
    await property_repo.create_property(db_session, prop1)
    await property_repo.create_property(db_session, prop2)
    
    # Search by city
    results = await property_repo.search_properties(db_session, city="Moscow")
    
    assert len(results) == 1
    assert results[0].city == "Moscow"


@pytest.mark.asyncio
async def test_search_properties_by_price_range(db_session: AsyncSession):
    """Test searching properties by price range."""
    # Create properties with different prices
    prop1 = PropertyCreate(
        source="test", external_id="test1", title="Cheap",
        price=30000.0, location={"city": "Moscow"}
    )
    prop2 = PropertyCreate(
        source="test", external_id="test2", title="Expensive",
        price=100000.0, location={"city": "Moscow"}
    )
    
    await property_repo.create_property(db_session, prop1)
    await property_repo.create_property(db_session, prop2)
    
    # Search in range
    results = await property_repo.search_properties(
        db_session, city="Moscow", min_price=40000.0, max_price=120000.0
    )
    
    assert len(results) == 1
    assert results[0].price == 100000.0


@pytest.mark.asyncio
async def test_track_price_change(db_session: AsyncSession, sample_property_data):
    """Test tracking price changes."""
    # Create property
    property = await property_repo.create_property(db_session, sample_property_data)
    
    # Track price change
    history = await property_repo.track_price_change(
        db_session, property.id, 50000.0, 55000.0
    )
    
    assert history.property_id == property.id
    assert history.old_price == 50000.0
    assert history.new_price == 55000.0
    assert history.price_change == 5000.0
    assert history.price_change_percent == 10.0


@pytest.mark.asyncio
async def test_get_price_history(db_session: AsyncSession, sample_property_data):
    """Test getting price history."""
    # Create property
    property = await property_repo.create_property(db_session, sample_property_data)
    
    # Create price changes
    await property_repo.track_price_change(db_session, property.id, 50000.0, 55000.0)
    await property_repo.track_price_change(db_session, property.id, 55000.0, 60000.0)
    
    # Get history
    history = await property_repo.get_price_history(db_session, property.id)
    
    assert len(history) == 2
    assert history[0].new_price == 60000.0  # Most recent first


@pytest.mark.asyncio
async def test_track_property_view(db_session: AsyncSession, sample_property_data):
    """Test tracking property views."""
    # Create property
    property = await property_repo.create_property(db_session, sample_property_data)
    
    # Track view
    view = await property_repo.track_property_view(
        db_session,
        property.id,
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0"
    )
    
    assert view.property_id == property.id
    assert view.ip_address == "192.168.1.1"


@pytest.mark.asyncio
async def test_get_property_view_count(db_session: AsyncSession, sample_property_data):
    """Test getting view count for a property."""
    # Create property
    property = await property_repo.create_property(db_session, sample_property_data)
    
    # Track multiple views
    for i in range(5):
        await property_repo.track_property_view(
            db_session, property.id, ip_address=f"192.168.1.{i}"
        )
    
    # Get count
    count = await property_repo.get_property_view_count(db_session, property.id)
    
    assert count == 5


@pytest.mark.asyncio
async def test_track_search_query(db_session: AsyncSession):
    """Test tracking search queries."""
    query = await property_repo.track_search_query(
        db_session,
        city="Moscow",
        property_type="apartment",
        min_price=30000.0,
        max_price=70000.0,
        results_count=10
    )
    
    assert query.city == "Moscow"
    assert query.property_type == "apartment"
    assert query.results_count == 10


@pytest.mark.asyncio
async def test_bulk_upsert_properties(db_session: AsyncSession):
    """Test bulk upserting properties."""
    properties = [
        PropertyCreate(
            source="test", external_id=f"test{i}", title=f"Property {i}",
            price=50000.0 + i * 1000, location={"city": "Moscow"}
        )
        for i in range(5)
    ]
    
    result = await property_repo.bulk_upsert_properties(db_session, properties)
    
    assert result["created"] == 5
    assert result["updated"] == 0
    assert result["errors"] == 0
    
    # Update same properties
    updated_properties = [
        prop.model_copy(update={"price": prop.price + 5000})
        for prop in properties
    ]
    
    result2 = await property_repo.bulk_upsert_properties(db_session, updated_properties)
    
    assert result2["created"] == 0
    assert result2["updated"] == 5


@pytest.mark.asyncio
async def test_get_property_statistics(db_session: AsyncSession):
    """Test getting property statistics."""
    # Create properties
    for i in range(5):
        prop = PropertyCreate(
            source="test", external_id=f"test{i}", title=f"Property {i}",
            price=40000.0 + i * 10000, area=50.0 + i * 10,
            location={"city": "Moscow"}
        )
        await property_repo.create_property(db_session, prop)
    
    # Get statistics
    stats = await property_repo.get_property_statistics(db_session, city="Moscow")
    
    assert stats["total"] == 5
    assert stats["avg_price"] == 60000.0
    assert stats["min_price"] == 40000.0
    assert stats["max_price"] == 80000.0
