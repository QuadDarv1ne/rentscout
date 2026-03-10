"""
Tests for Materialized Views repository.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.materialized_views import (
    get_property_stats_by_location,
    get_price_trends,
    get_popular_searches,
    get_property_view_stats,
    refresh_materialized_view,
    get_all_materialized_views,
)


@pytest.fixture
def mock_db():
    """Create mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_get_property_stats_by_location(mock_db):
    """Test getting property stats from materialized view."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        MagicMock(
            city="Москва",
            district="Центральный",
            source="avito",
            property_count=100,
            avg_price=50000.0,
            min_price=30000.0,
            max_price=100000.0,
            avg_area=45.5,
            avg_rooms=2.0,
            avg_price_per_sqm=1100.0,
            active_count=95,
            verified_count=50,
        )
    ]
    mock_db.execute.return_value = mock_result
    
    result = await get_property_stats_by_location(mock_db, city="Москва")
    
    assert len(result) == 1
    assert result[0]["city"] == "Москва"
    assert result[0]["property_count"] == 100
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_property_stats_with_filters(mock_db):
    """Test getting property stats with multiple filters."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    result = await get_property_stats_by_location(
        mock_db,
        city="Москва",
        district="Центральный",
        source="cian"
    )
    
    assert result == []
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_price_trends(mock_db):
    """Test getting price trends from materialized view."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        MagicMock(
            date="2026-03-10",
            city="Москва",
            rooms=2,
            property_count=50,
            avg_price=55000.0,
            min_price=40000.0,
            max_price=80000.0,
            avg_area=50.0,
            median_price=53000.0,
        )
    ]
    mock_db.execute.return_value = mock_result
    
    result = await get_price_trends(mock_db, city="Москва", days=30)
    
    assert len(result) == 1
    assert result[0]["city"] == "Москва"
    assert result[0]["avg_price"] == 55000.0
    mock_db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_price_trends_with_rooms(mock_db):
    """Test getting price trends filtered by rooms."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    result = await get_price_trends(mock_db, rooms=3, days=7)
    
    assert result == []


@pytest.mark.asyncio
async def test_get_popular_searches(mock_db):
    """Test getting popular searches from materialized view."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        MagicMock(
            city="Москва",
            property_type="Квартира",
            search_date="2026-03-10",
            search_count=500,
            avg_results=100.0,
            unique_users=250,
        )
    ]
    mock_db.execute.return_value = mock_result
    
    result = await get_popular_searches(mock_db, city="Москва", days=7, limit=20)
    
    assert len(result) == 1
    assert result[0]["search_count"] == 500
    assert result[0]["unique_users"] == 250


@pytest.mark.asyncio
async def test_get_property_view_stats(mock_db):
    """Test getting property view stats from materialized view."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        MagicMock(
            property_id=123,
            view_date="2026-03-10",
            view_count=150,
            unique_visitors=100,
        )
    ]
    mock_db.execute.return_value = mock_result
    
    result = await get_property_view_stats(mock_db, property_id=123, days=7)
    
    assert len(result) == 1
    assert result[0]["property_id"] == 123
    assert result[0]["view_count"] == 150


@pytest.mark.asyncio
async def test_get_property_view_stats_all(mock_db):
    """Test getting all property view stats."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    result = await get_property_view_stats(mock_db, days=30)
    
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_refresh_materialized_view(mock_db):
    """Test refreshing materialized view."""
    mock_db.execute.return_value = MagicMock()
    
    result = await refresh_materialized_view(mock_db, "mv_property_stats_by_location")
    
    assert result is True
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_materialized_view_concurrently(mock_db):
    """Test refreshing materialized view concurrently."""
    mock_db.execute.return_value = MagicMock()
    
    result = await refresh_materialized_view(
        mock_db,
        "mv_property_stats_by_location",
        concurrently=True
    )
    
    assert result is True


@pytest.mark.asyncio
async def test_refresh_materialized_view_error(mock_db):
    """Test refreshing materialized view with error."""
    mock_db.execute.side_effect = Exception("Database error")
    
    with pytest.raises(Exception):
        await refresh_materialized_view(mock_db, "mv_test")
    
    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_materialized_views(mock_db):
    """Test getting all materialized views."""
    mock_result = MagicMock()
    mock_result.all.return_value = [
        MagicMock(
            schemaname="public",
            view_name="mv_property_stats_by_location",
            matviewowner="postgres",
            hasindexes=True,
        ),
        MagicMock(
            schemaname="public",
            view_name="mv_price_trends_daily",
            matviewowner="postgres",
            hasindexes=True,
        ),
    ]
    mock_db.execute.return_value = mock_result
    
    result = await get_all_materialized_views(mock_db)
    
    assert len(result) == 2
    assert result[0]["view_name"] == "mv_property_stats_by_location"
    assert result[0]["has_indexes"] is True


@pytest.mark.asyncio
async def test_get_property_stats_no_filters(mock_db):
    """Test getting property stats without any filters."""
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    result = await get_property_stats_by_location(mock_db)
    
    assert isinstance(result, list)
    mock_db.execute.assert_called_once()
