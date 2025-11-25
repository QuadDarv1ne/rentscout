from app.parsers.avito.parser import AvitoParser

def get_parsers():
    """Return a list of available parsers."""
    return [AvitoParser()]