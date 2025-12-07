"""
End-to-end style tests for parser stack and search service aggregation.
These tests mock external HTTP requests but exercise parser logic and aggregation flow.
"""
import pytest
from unittest.mock import AsyncMock

from app.models.schemas import PropertyCreate
from app.parsers.avito.parser import AvitoParser
from app.services.search import SearchService


@pytest.mark.asyncio
async def test_avito_parse_internal_with_mocked_http(monkeypatch):
    """Avito parser should parse mocked HTML end-to-end without real HTTP."""
    parser = AvitoParser()

    sample_html = """
    <div data-marker="item" data-item-id="12345">
        <h3 itemprop="name">2-к квартира, 45 м²</h3>
        <span itemprop="price" content="4500">4 500 ₽/мес.</span>
        <a data-marker="item-title" href="/moskva/kvartiry/12345">Подробнее</a>
        <img src="https://example.com/photo1.jpg" />
    </div>
    """

    # Dummy response and client to bypass real network
    class DummyResponse:
        def __init__(self, text: str):
            self.text = text

        def raise_for_status(self):
            return None

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            return DummyResponse(sample_html)

    # Monkeypatch external dependencies
    monkeypatch.setattr("httpx.AsyncClient", DummyClient)
    monkeypatch.setattr("app.parsers.avito.parser.rate_limiter.acquire", AsyncMock())

    results = await parser._parse_internal("moskva", {"type": "Квартира"})

    assert len(results) == 1
    prop = results[0]
    assert isinstance(prop, PropertyCreate)
    assert prop.source == "avito"
    assert prop.external_id == "12345"
    assert prop.price == 4500.0
    assert prop.rooms == 2
    assert prop.area == 45.0
    assert prop.photos == ["https://example.com/photo1.jpg"]


@pytest.mark.asyncio
async def test_search_service_combines_parsers(monkeypatch):
    """SearchService should merge results from multiple parsers and persist them."""
    service = SearchService()

    props_avito = [
        PropertyCreate(source="avito", external_id="a1", title="Avito Flat", price=40000.0),
    ]
    props_cian = [
        PropertyCreate(source="cian", external_id="c1", title="Cian Flat", price=50000.0),
        PropertyCreate(source="cian", external_id="c2", title="Cian Flat 2", price=55000.0),
    ]

    # Patch parser parse methods
    service.parsers[0].parse = AsyncMock(return_value=props_avito)
    service.parsers[1].parse = AsyncMock(return_value=props_cian)

    saved = {}

    async def fake_save(properties):
        saved["count"] = len(properties)

    monkeypatch.setattr("app.services.search.save_properties", fake_save)

    results = await service.search("Москва", "Квартира")

    assert len(results) == 3
    assert saved.get("count") == 3
    sources = [p.source for p in results]
    assert sources.count("avito") == 1
    assert sources.count("cian") == 2


@pytest.mark.asyncio
async def test_search_service_handles_parser_failure(monkeypatch):
    """If one parser fails, results from others should still be returned."""
    service = SearchService()

    props_avito = [PropertyCreate(source="avito", external_id="a1", title="Avito Flat", price=40000.0)]

    async def failing_parse(*args, **kwargs):
        raise RuntimeError("parser down")

    service.parsers[0].parse = AsyncMock(side_effect=failing_parse)
    service.parsers[1].parse = AsyncMock(return_value=props_avito)

    saved = {}

    async def fake_save(properties):
        saved["count"] = len(properties)

    monkeypatch.setattr("app.services.search.save_properties", fake_save)

    results = await service.search("Москва", "Квартира")

    assert len(results) == 1
    assert saved.get("count") == 1
    assert results[0].source == "avito"
