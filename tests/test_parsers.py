import pytest
from app.parsers.avito.parser import AvitoParser
from app.parsers.cian.parser import CianParser


@pytest.mark.asyncio
async def test_avito_parser_initialization():
    parser = AvitoParser()
    assert parser.name == "AvitoParser"


@pytest.mark.asyncio
async def test_cian_parser_initialization():
    parser = CianParser()
    assert parser.name == "CianParser"


@pytest.mark.asyncio
async def test_parser_validate_params():
    parser = AvitoParser()
    params = {"min_price": 10000, "max_price": 50000}
    is_valid = await parser.validate_params(params)
    assert isinstance(is_valid, bool)
