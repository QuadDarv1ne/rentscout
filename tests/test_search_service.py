import pytest
from app.services.search import SearchService


@pytest.mark.asyncio
async def test_search_service_initialization():
    service = SearchService()
    assert len(service.parsers) > 0
    assert service.duplicate_filter is not None


@pytest.mark.asyncio
async def test_search_service_has_parsers():
    service = SearchService()
    parser_names = [p.name for p in service.parsers]
    assert "AvitoParser" in parser_names
    assert "CianParser" in parser_names
