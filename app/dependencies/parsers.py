from app.parsers.avito.parser import AvitoParser
from app.parsers.cian.parser import CianParser


def get_parsers():
    """Return a list of available parsers."""
    return [AvitoParser(), CianParser()]