import pytest
from unittest.mock import AsyncMock, patch
from app.db.crud import save_properties
from app.models.schemas import PropertyCreate

@pytest.mark.asyncio
async def test_save_properties_success():
    """Test successful saving of properties to Elasticsearch."""
    # Create test properties
    properties = [
        PropertyCreate(
            source="avito",
            external_id="12345",
            title="Тестовая квартира",
            price=3000,
            rooms=1,
            area=30
        )
    ]
    
    # Mock the Elasticsearch client
    with patch('app.db.crud.es') as mock_es:
        mock_es.index = AsyncMock()
        
        # Call the function
        await save_properties(properties)
        
        # Verify the Elasticsearch index method was called correctly
        mock_es.index.assert_called_once_with(
            index="properties",
            body={
                "source": "avito",
                "external_id": "12345",
                "title": "Тестовая квартира",
                "price": 3000,
                "rooms": 1,
                "area": 30,
                "location": None,
                "photos": []
            },
            id="12345"
        )

@pytest.mark.asyncio
async def test_save_properties_multiple():
    """Test saving multiple properties to Elasticsearch."""
    # Create multiple test properties
    properties = [
        PropertyCreate(
            source="avito",
            external_id="12345",
            title="Первая квартира",
            price=3000,
            rooms=1,
            area=30
        ),
        PropertyCreate(
            source="avito",
            external_id="67890",
            title="Вторая квартира",
            price=4500,
            rooms=2,
            area=45
        )
    ]
    
    # Mock the Elasticsearch client
    with patch('app.db.crud.es') as mock_es:
        mock_es.index = AsyncMock()
        
        # Call the function
        await save_properties(properties)
        
        # Verify the Elasticsearch index method was called twice
        assert mock_es.index.call_count == 2
        
        # Verify the calls were made with correct parameters
        mock_es.index.assert_any_call(
            index="properties",
            body={
                "source": "avito",
                "external_id": "12345",
                "title": "Первая квартира",
                "price": 3000,
                "rooms": 1,
                "area": 30,
                "location": None,
                "photos": []
            },
            id="12345"
        )
        
        mock_es.index.assert_any_call(
            index="properties",
            body={
                "source": "avito",
                "external_id": "67890",
                "title": "Вторая квартира",
                "price": 4500,
                "rooms": 2,
                "area": 45,
                "location": None,
                "photos": []
            },
            id="67890"
        )

@pytest.mark.asyncio
async def test_save_properties_error_handling():
    """Test error handling when saving properties fails."""
    # Create test properties
    properties = [
        PropertyCreate(
            source="avito",
            external_id="12345",
            title="Тестовая квартира",
            price=3000,
            rooms=1,
            area=30
        )
    ]
    
    # Mock the Elasticsearch client to raise an exception
    with patch('app.db.crud.es') as mock_es:
        mock_es.index = AsyncMock(side_effect=Exception("Elasticsearch error"))
        
        # Call the function and expect it to raise an exception
        with pytest.raises(Exception, match="Elasticsearch error"):
            await save_properties(properties)