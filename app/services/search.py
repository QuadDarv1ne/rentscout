import logging
from typing import List
from app.models.schemas import PropertyCreate, Property
from app.parsers.avito.parser import AvitoParser
# from app.parsers.cian.parser import CianParser  # TODO: Implement CianParser
from app.db.crud import save_properties

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self):
        self.parsers = [AvitoParser()]
        # TODO: Add CianParser when implemented
        # self.parsers = [AvitoParser(), CianParser()]

    async def search(self, city: str) -> List[Property]:
        all_properties = []
        for parser in self.parsers:
            try:
                results = await parser.parse_listing(city)
                all_properties.extend(results)
            except Exception as e:
                logger.error(f"Parser {parser.__class__.__name__} failed: {e}")
        
        try:
            await save_properties(all_properties)
        except Exception as e:
            logger.error(f"Error saving properties: {e}")
            # Don't raise the exception, as we still want to return the properties
        
        return all_properties
