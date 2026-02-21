import asyncio
import logging
import hashlib
import time
from typing import List, Dict, Any

from app.db.crud import save_properties
from app.db.repositories.property import bulk_create_properties
from app.db.batch_insert import bulk_upsert_with_deduplication
from app.models.schemas import Property, PropertyCreate
from app.parsers.avito.parser import AvitoParser
from app.parsers.cian.parser import CianParser
from app.parsers.domofond.parser import DomofondParser
from app.parsers.yandex_realty.parser import YandexRealtyParser
from app.parsers.domclick.parser import DomclickParser
from app.parsers.base_parser import BaseParser
from app.utils.parser_errors import ErrorClassifier, ErrorSeverity
from app.utils.metrics import metrics_collector
from app.utils.performance_profiling import profile_function
from app.utils.circuit_breaker import ParserCircuitBreaker
from app.utils.bloom_filter import DuplicateFilter
from app.core.config import settings

logger = logging.getLogger(__name__)


class SearchService:
    """Сервис поиска недвижимости с поддержкой множества парсеров."""

    def __init__(self) -> None:
        """Инициализация сервиса поиска."""
        self.parsers: List[BaseParser] = [AvitoParser(), CianParser(), DomofondParser(), YandexRealtyParser(), DomclickParser()]
        self.duplicate_filter = DuplicateFilter(
            expected_items=100000,
            false_positive_rate=0.001,  # 0.1% FP rate
            use_exact_check=True,
            exact_check_threshold=5000
        )
        logger.info("SearchService initialized with circuit breaker and bloom filter")

    @profile_function
    async def search(self, city: str, property_type: str = "Квартира") -> List[Property]:
        """
        Поиск недвижимости с использованием параллельного выполнения парсеров.
        Использует circuit breaker для защиты от сбоев и bloom filter для дедупликации.

        Args:
            city: Город для поиска
            property_type: Тип недвижимости

        Returns:
            Список найденных объектов недвижимости
        """
        start_time = time.time()

        # Выполняем парсеры параллельно с индивидуальными таймаутами
        individual_timeout = getattr(settings, 'PARSER_TIMEOUT', 15.0)
        overall_timeout = getattr(settings, 'SEARCH_TIMEOUT', 45.0)

        # Convert to float as settings are integers
        individual_timeout = float(individual_timeout)
        overall_timeout = float(overall_timeout)

        # Используем circuit breaker для каждого парсера
        parser_tasks = [
            asyncio.wait_for(
                ParserCircuitBreaker.call_parser(
                    parser.__class__.__name__,
                    self._parse_with_parser,
                    parser, city, property_type
                ),
                timeout=individual_timeout
            )
            for parser in self.parsers
        ]

        # Ждем завершения всех задач с общим таймаутом
        try:
            raw_results = await asyncio.wait_for(
                asyncio.gather(*parser_tasks, return_exceptions=True),
                timeout=overall_timeout
            )
            # Process results, handling TimeoutError exceptions
            parser_results = []
            for i, result in enumerate(raw_results):
                if isinstance(result, asyncio.TimeoutError):
                    parser_name = self.parsers[i].__class__.__name__
                    logger.warning(f"Parser {parser_name} timed out for {city}")
                    parser_results.append([])  # Пустой результат вместо ошибки
                elif isinstance(result, Exception):
                    parser_name = self.parsers[i].__class__.__name__
                    logger.warning(f"Parser {parser_name} failed: {result}")
                    parser_results.append([])
                else:
                    parser_results.append(result)
        except asyncio.TimeoutError:
            logger.warning(f"Overall search timeout exceeded for {city} (timeout: {overall_timeout}s)")
            parser_results = []

        # Собираем результаты
        all_properties = []
        for i, result in enumerate(parser_results):
            if isinstance(result, Exception):
                parser_name = self.parsers[i].__class__.__name__
                classification = ErrorClassifier.classify(result)
                logger.warning(f"Error in {parser_name} ({classification['type']}): {result}")
                metrics_collector.record_parser_error(parser_name, classification.get("type", "Unknown"))
            elif result:  # Не пустой список
                all_properties.extend(result)

        # Используем bloom filter для дедупликации
        unique_properties = []
        duplicates_count = 0

        for prop in all_properties:
            # Создаем уникальный ключ из источника и внешнего ID
            key = f"{prop.source}:{prop.external_id}"

            if not self.duplicate_filter.is_duplicate(key):
                unique_properties.append(prop)
            else:
                duplicates_count += 1

        # Сохраняем свойства в базу данных с помощью bulk операции для лучшей производительности
        if unique_properties:
            try:
                # Используем оптимизированный batch insert с deduplication
                stats = await bulk_upsert_with_deduplication(
                    db=None,  # TODO: Передать db session когда будет доступен
                    properties=unique_properties
                )
                
                logger.info(
                    f"Database upsert completed: {stats['inserted']} inserted, "
                    f"{stats['updated']} updated, {stats['duplicates_removed']} DB duplicates removed"
                )
                
                for prop in unique_properties:
                    metrics_collector.record_property_processed(prop.source, "saved")
                    
            except Exception as e:
                logger.error(f"Error saving properties to database: {e}", exc_info=True)
                metrics_collector.record_error("database_save")

        # Записываем метрики
        duration = time.time() - start_time
        metrics_collector.record_search_operation(city, len(unique_properties), duration)
        metrics_collector.record_duplicates_removed(duplicates_count)

        logger.info(
            f"Search completed for {city}: found {len(all_properties)} properties, "
            f"{len(unique_properties)} unique, {duplicates_count} duplicates removed "
            f"(bloom filter: {self.duplicate_filter.get_stats()})"
        )

        return unique_properties

    @profile_function
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