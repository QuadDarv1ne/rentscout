import pytest
from unittest.mock import patch, AsyncMock

from app.db.crud import save_properties
from app.models.schemas import PropertyCreate


@pytest.mark.asyncio
async def test_save_properties_success():
    """Test saving a single property to Elasticsearch."""
    # Create a test property
    properties = [
        PropertyCreate(
            source="avito",
            external_id="12345",
            title="Тестовая квартира",
            price=3000.0,
            rooms=1,
            area=30.0,
            link=None
        )
    ]

    # Mock the Elasticsearch client
    with patch('app.db.crud.es') as mock_es:
        mock_es.index = AsyncMock()

        # Call the function
        await save_properties(properties)

        # Verify the Elasticsearch index method was called once
        assert mock_es.index.call_count == 1
        
        # Check that call was made with correct index and id
        call_args = mock_es.index.call_args
        assert call_args.kwargs['index'] == "properties"
        assert call_args.kwargs['id'] == "12345"
        
        # Verify essential fields are in the body
        body = call_args.kwargs['body']
        assert body['source'] == "avito"
        assert body['external_id'] == "12345"
        assert body['title'] == "Тестовая квартира"
        assert body['price'] == 3000.0
        assert body['rooms'] == 1
        assert body['area'] == 30.0


@pytest.mark.asyncio
async def test_save_properties_multiple():
    """Test saving multiple properties to Elasticsearch."""
    # Create multiple test properties
    properties = [
        PropertyCreate(
            source="avito",
            external_id="12345",
            title="Первая квартира",
            price=3000.0,
            rooms=1,
            area=30.0,
            link=None
        ),
        PropertyCreate(
            source="avito",
            external_id="67890",
            title="Вторая квартира",
            price=4500.0,
            rooms=2,
            area=45.0,
            link=None
        ),
    ]

    # Mock the Elasticsearch client
    with patch('app.db.crud.es') as mock_es:
        mock_es.index = AsyncMock()

        # Call the function
        await save_properties(properties)

        # Verify the Elasticsearch index method was called twice
        assert mock_es.index.call_count == 2
        
        # Get both calls
        calls = mock_es.index.call_args_list
        
        # Verify first call
        assert calls[0].kwargs['index'] == "properties"
        assert calls[0].kwargs['id'] == "12345"
        assert calls[0].kwargs['body']['title'] == "Первая квартира"
        
        # Verify second call
        assert calls[1].kwargs['index'] == "properties"
        assert calls[1].kwargs['id'] == "67890"
        assert calls[1].kwargs['body']['title'] == "Вторая квартира"


@pytest.mark.asyncio
async def test_save_properties_error_handling():
    """Test error handling when saving properties fails."""
    # Create test properties
    properties = [
        PropertyCreate(
            source="avito",
            external_id="12345",
            title="Тестовая квартира",
            price=3000.0,
            rooms=1,
            area=30.0,
            link=None
        )
    ]

    # Mock the Elasticsearch client to raise an exception
    with patch('app.db.crud.es') as mock_es:
        mock_es.index = AsyncMock(side_effect=Exception("Elasticsearch error"))

        # Call the function and expect it to raise an exception
        with pytest.raises(Exception, match="Elasticsearch error"):
            await save_properties(properties)