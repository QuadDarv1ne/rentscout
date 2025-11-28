import asyncio
import logging
from typing import List

# from app.parsers.cian.parser import CianParser  # TODO: Implement CianParser
from app.db.crud import save_properties
from app.models.schemas import Property, PropertyCreate
from app.parsers.avito.parser import AvitoParser

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self):
        self.parsers = [AvitoParser()]
        # TODO: Add CianParser when implemented
        # self.parsers = [AvitoParser(), CianParser()]

    async def search(self, city: str, property_type: str = "Квартира") -> List[Property]:
        """
        Поиск недвижимости с использованием параллельного выполнения парсеров.

        Args:
            city: Город для поиска
            property_type: Тип недвижимости

        Returns:
            Список найденных объектов недвижимости
        """
        # Выполняем парсеры параллельно
        parser_tasks = [self._parse_with_parser(parser, city, property_type) for parser in self.parsers]

        # Ждем завершения всех задач
        parser_results = await asyncio.gather(*parser_tasks, return_exceptions=True)

        # Собираем результаты, игнорируя ошибки
        all_properties = []
        for i, result in enumerate(parser_results):
            if isinstance(result, Exception):
                parser_name = self.parsers[i].__class__.__name__
                logger.error(f"Parser {parser_name} failed: {result}")
            else:
                all_properties.extend(result)

        try:
            await save_properties(all_properties)
        except Exception as e:
            logger.error(f"Error saving properties: {e}")
            # Don't raise the exception, as we still want to return the properties

        # Конвертируем PropertyCreate объекты в Property объекты
        result_properties = []
        for prop in all_properties:
            # Generate a simple ID based on source and external_id
            prop_id = f"{prop.source}_{prop.external_id}"
            property_obj = Property(
                id=prop_id,
                source=prop.source,
                external_id=prop.external_id,
                title=prop.title,
                price=prop.price,
                rooms=prop.rooms,
                area=prop.area,
                location=prop.location,
                photos=prop.photos,
                description=prop.description,
            )
            result_properties.append(property_obj)

        return result_properties

    async def _parse_with_parser(self, parser, city: str, property_type: str) -> List[PropertyCreate]:
        """
        Выполнение парсинга с конкретным парсером.

        Args:
            parser: Экземпляр парсера
            city: Город для поиска
            property_type: Тип недвижимости

        Returns:
            Список найденных объектов недвижимости
        """
        try:
            results = await parser.parse(city, {"type": property_type})
            return results
        except Exception as e:
            logger.error(f"Parser {parser.__class__.__name__} failed: {e}")
            raise
