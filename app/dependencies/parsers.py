from app.parsers.avito.parser import AvitoParser
from app.parsers.cian.parser import CianParser
from app.parsers.domofond.parser import DomofondParser
from app.parsers.yandex_realty.parser import YandexRealtyParser


def get_parsers():
    """Return a list of available parsers."""
    return [AvitoParser(), CianParser(), DomofondParser(), YandexRealtyParser()]