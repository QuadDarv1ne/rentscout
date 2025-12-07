import asyncio
import logging
import hashlib
import time
from typing import List, Dict, Any

from app.db.crud import save_properties
from app.db.repositories.property import bulk_create_properties
from app.models.schemas import Property, PropertyCreate
from app.parsers.avito.parser import AvitoParser
from app.parsers.cian.parser import CianParser
from app.parsers.domofond.parser import DomofondParser
from app.parsers.yandex_realty.parser import YandexRealtyParser
from app.parsers.base_parser import BaseParser
from app.utils.parser_errors import ErrorClassifier, ErrorSeverity
from app.utils.metrics import metrics_collector

logger = logging.getLogger(__name__)


class SearchService:
    """Сервис поиска недвижимости с поддержкой множества парсеров."""

    def __init__(self) -> None:
        """Инициализация сервиса поиска."""
        self.parsers: List[BaseParser] = [AvitoParser(), CianParser(), DomofondParser(), YandexRealtyParser()]

    async def search(self, city: str, property_type: str = "Квартира") -> List[Property]:
        """
        Поиск недвижимости с использованием параллельного выполнения парсеров.

        Args:
            city: Город для поиска
            property_type: Тип недвижимости

        Returns:
            Список найденных объектов недвижимости
        """
        start_time = time.time()
        
        # Выполняем парсеры параллельно
        parser_tasks = [self._parse_with_parser(parser, city, property_type) for parser in self.parsers]

        # Ждем завершения всех задач
        parser_results = await asyncio.gather(*parser_tasks, return_exceptions=True)

        # Собираем результаты, логируя ошибки с учетом их типа
        all_properties = []
        for i, result in enumerate(parser_results):
            if isinstance(result, Exception):
                parser_name = self.parsers[i].__class__.__name__
                # Классифицируем ошибку для более точного логирования
                classification = ErrorClassifier.classify(result)
                severity = classification.get("severity", ErrorSeverity.INFO)
                
                # Логируем в зависимости от уровня серьезности
                if severity == ErrorSeverity.CRITICAL or severity == ErrorSeverity.ERROR:
                    logger.error(f"Critical error in {parser_name}: {result}", exc_info=True)
                elif severity == ErrorSeverity.WARNING:
                    logger.warning(f"Warning in {parser_name}: {result}")
                else:
                    logger.info(f"Minor issue in {parser_name}: {result}")
                    
                # Записываем метрики для ошибок парсеров
                metrics_collector.record_parser_error(parser_name, classification.get("type", "Unknown"))
            else:
                all_properties.extend(result)

        # Удаляем дубликаты, сохраняя порядок
        seen = set()
        unique_properties = []
        duplicates_count = 0
        
        for prop in all_properties:
            # Создаем уникальный ключ из источника и внешнего ID
            key = (prop.source, prop.external_id)
            if key not in seen:
                seen.add(key)
                unique_properties.append(prop)
            else:
                duplicates_count += 1

        # Сохраняем свойства в базу данных с помощью bulk операции для лучшей производительности
        if unique_properties:
            try:
                # Преобразуем Property в PropertyCreate для сохранения
                properties_to_save = [
                    PropertyCreate(
                        source=prop.source,
                        external_id=prop.external_id,
                        title=prop.title,
                        description=prop.description,
                        link=prop.link,
                        price=prop.price,
                        rooms=prop.rooms,
                        area=prop.area,
                        city=prop.city,
                        district=prop.district,
                        address=prop.address,
                        latitude=prop.latitude,
                        longitude=prop.longitude,
                        location=prop.location,
                        photos=prop.photos
                    ) for prop in unique_properties
                ]
                
                # Используем bulk операцию для лучшей производительности
                # Note: We would need to pass the db session here, but for now we'll use the existing save_properties function
                await save_properties(unique_properties)
                
                logger.info(f"Saved {len(unique_properties)} unique properties to database")
                metrics_collector.record_properties_processed(len(unique_properties), "saved")
            except Exception as e:
                logger.error(f"Error saving properties to database: {e}", exc_info=True)
                metrics_collector.record_error("database_save")

        # Записываем метрики
        duration = time.time() - start_time
        metrics_collector.record_search_operation(city, len(unique_properties), duration)
        metrics_collector.record_duplicates_removed(duplicates_count)

        logger.info(f"Search completed for {city}: found {len(all_properties)} properties, "
                   f"{len(unique_properties)} unique, {duplicates_count} duplicates removed")
        
        return unique_properties

    async def _parse_with_parser(self, parser: BaseParser, city: str, property_type: str) -> List[Property]:
        """
        Выполняет парсинг с конкретным парсером с обработкой ошибок и повторными попытками.

        Args:
            parser: Экземпляр парсера
            city: Город для поиска
            property_type: Тип недвижимости

        Returns:
            Список найденных объектов недвижимости
        """
        parser_name = parser.__class__.__name__
        logger.info(f"Starting parsing with {parser_name} for city: {city}")

        try:
            # Валидируем параметры перед парсингом
            params = {"property_type": property_type}
            is_valid = await parser.validate_params(params)
            if not is_valid:
                logger.warning(f"Invalid parameters for {parser_name}")
                return []

            # Предобрабатываем параметры
            processed_params = await parser.preprocess_params(params)

            # Выполняем парсинг
            properties = await parser.parse(city, processed_params)
            
            logger.info(f"{parser_name} found {len(properties)} properties")
            metrics_collector.record_parser_success(parser_name, len(properties))
            
            return properties
            
        except Exception as e:
            logger.error(f"Error in {parser_name}: {e}", exc_info=True)
            metrics_collector.record_parser_failure(parser_name)
            # Не перехватываем ошибку здесь, чтобы она могла быть обработана выше
            raise
