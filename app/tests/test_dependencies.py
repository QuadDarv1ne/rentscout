import pytest

from app.dependencies.parsers import get_parsers
from app.parsers.avito.parser import AvitoParser


def test_get_parsers():
    """Тест функции get_parsers."""
    # Получаем список парсеров
    parsers = get_parsers()

    # Проверяем, что список не пустой
    assert len(parsers) > 0

    # Проверяем, что все элементы являются экземплярами парсеров
    for parser in parsers:
        assert isinstance(parser, AvitoParser) or hasattr(parser, 'parse')


def test_get_parsers_returns_list():
    """Тест, что get_parsers возвращает список."""
    parsers = get_parsers()
    assert isinstance(parsers, list)


def test_get_parsers_content():
    """Тест содержимого, возвращаемого get_parsers."""
    parsers = get_parsers()

    # Проверяем, что в списке есть хотя бы один парсер
    assert len(parsers) >= 1

    # Проверяем, что первый парсер является экземпляром AvitoParser
    assert isinstance(parsers[0], AvitoParser)

    # Проверяем, что у парсера есть метод parse
    assert hasattr(parsers[0], 'parse')
    assert callable(getattr(parsers[0], 'parse'))

    # Проверяем, что у парсера есть метод validate_params
    assert hasattr(parsers[0], 'validate_params')
    assert callable(getattr(parsers[0], 'validate_params'))
