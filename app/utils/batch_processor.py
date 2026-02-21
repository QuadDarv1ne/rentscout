"""
Batch processing утилита для эффективного парсинга больших объёмов данных.

Позволяет:
- Пакетную обработку множества локаций
- Параллельный парсинг с контролем нагрузки
- Прогресс-бар для отслеживания
- Автоматический retry при ошибках
- Сохранение промежуточных результатов
"""
import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from app.parsers.optimized_base_parser import OptimizedBaseParser
from app.models.schemas import PropertyCreate
from app.utils.parser_monitor import monitor


@dataclass
class BatchConfig:
    """Конфигурация batch processing."""
    max_concurrent_parsers: int = 3
    max_concurrent_locations: int = 10
    retry_failed: bool = True
    max_retries: int = 2
    save_intermediate: bool = True
    intermediate_save_interval: int = 100  # сохранять каждые N результатов


class BatchProcessor:
    """
    Процессор для пакетной обработки парсинга.
    
    Оптимизирован для обработки больших объёмов данных
    с контролем нагрузки и отслеживанием прогресса.
    """
    
    def __init__(self, config: Optional[BatchConfig] = None):
        """
        Инициализация процессора.
        
        Args:
            config: Конфигурация batch processing
        """
        self.config = config or BatchConfig()
        self._results: Dict[str, List[PropertyCreate]] = {}
        self._errors: Dict[str, List[Dict[str, Any]]] = {}
        self._progress: Dict[str, int] = {}
        
    async def process_multiple_parsers(
        self,
        parsers: List[OptimizedBaseParser],
        locations: List[str],
        params: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, Dict[str, List[PropertyCreate]]]:
        """
        Обработка множественных парсеров для множественных локаций.
        
        Args:
            parsers: Список парсеров
            locations: Список локаций
            params: Параметры поиска
            progress_callback: Callback для отслеживания прогресса
            
        Returns:
            Словарь {parser_name: {location: results}}
        """
        results = {}
        
        # Ограничение на количество одновременно работающих парсеров
        sem_parsers = asyncio.Semaphore(self.config.max_concurrent_parsers)
        
        async def process_single_parser(parser: OptimizedBaseParser):
            async with sem_parsers:
                async with parser:
                    parser_results = await self.process_locations(
                        parser=parser,
                        locations=locations,
                        params=params,
                        progress_callback=progress_callback
                    )
                    results[parser.name] = parser_results
                    
        # Запуск всех парсеров
        tasks = [process_single_parser(parser) for parser in parsers]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
        
    async def process_locations(
        self,
        parser: OptimizedBaseParser,
        locations: List[str],
        params: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, List[PropertyCreate]]:
        """
        Обработка множественных локаций одним парсером.
        
        Args:
            parser: Парсер
            locations: Список локаций
            params: Параметры поиска
            progress_callback: Callback для прогресса
            
        Returns:
            Словарь {location: results}
        """
        results = {}
        processed = 0
        total = len(locations)
        
        # Ограничение на количество одновременно обрабатываемых локаций
        sem_locations = asyncio.Semaphore(self.config.max_concurrent_locations)
        
        async def process_location(location: str):
            nonlocal processed
            
            async with sem_locations:
                start_time = asyncio.get_event_loop().time()
                success = False
                properties = []
                error = None
                
                try:
                    properties = await parser.parse(location, params)
                    success = True
                except Exception as e:
                    error = e
                    # Retry logic
                    if self.config.retry_failed:
                        for attempt in range(self.config.max_retries):
                            try:
                                await asyncio.sleep(2 ** attempt)  # exponential backoff
                                properties = await parser.parse(location, params)
                                success = True
                                error = None
                                break
                            except Exception as retry_error:
                                error = retry_error
                                
                duration = asyncio.get_event_loop().time() - start_time
                
                # Запись метрик
                monitor.record_request(
                    parser_name=parser.name,
                    duration=duration,
                    success=success,
                    properties_count=len(properties),
                    error=error
                )
                
                if success:
                    results[location] = properties
                else:
                    if parser.name not in self._errors:
                        self._errors[parser.name] = []
                    self._errors[parser.name].append({
                        'location': location,
                        'error': str(error),
                        'timestamp': datetime.now().isoformat()
                    })
                    
                processed += 1
                
                # Progress callback
                if progress_callback:
                    progress_callback(parser.name, processed, total)
                    
                # Intermediate save
                if self.config.save_intermediate and processed % self.config.intermediate_save_interval == 0:
                    await self._save_intermediate_results(parser.name, results)
                    
        # Запуск обработки всех локаций
        tasks = [process_location(location) for location in locations]
        await asyncio.gather(*tasks)
        
        return results
        
    async def _save_intermediate_results(
        self,
        parser_name: str,
        results: Dict[str, List[PropertyCreate]]
    ):
        """Сохранение промежуточных результатов."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"intermediate_{parser_name}_{timestamp}.json"
        filepath = Path("data") / "intermediate" / filename
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Конвертация в JSON-friendly формат
        json_data = {
            location: [prop.dict() for prop in properties]
            for location, properties in results.items()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
            
    def save_results(self, filepath: str, results: Dict[str, Any]):
        """
        Сохранение финальных результатов.
        
        Args:
            filepath: Путь к файлу
            results: Результаты для сохранения
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Подготовка данных
        export_data = {
            'timestamp': datetime.now().isoformat(),
            'total_parsers': len(results),
            'total_locations': sum(len(locs) for locs in results.values()),
            'results': {}
        }
        
        for parser_name, locations_data in results.items():
            export_data['results'][parser_name] = {
                location: [prop.dict() for prop in properties]
                for location, properties in locations_data.items()
            }
            
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
            
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики обработки."""
        total_properties = sum(
            len(props)
            for parser_results in self._results.values()
            for props in parser_results.values()
        )
        
        return {
            'total_results': len(self._results),
            'total_properties': total_properties,
            'total_errors': sum(len(errs) for errs in self._errors.values()),
            'errors_by_parser': {
                parser: len(errs) for parser, errs in self._errors.items()
            }
        }


async def batch_parse_example():
    """Пример использования batch processor."""
    from app.parsers.example_optimized_parser import ExampleOptimizedParser
    
    # Создание парсеров
    parsers = [ExampleOptimizedParser() for _ in range(3)]
    
    # Список локаций
    locations = [
        "Москва", "Санкт-Петербург", "Казань",
        "Новосибирск", "Екатеринбург", "Нижний Новгород"
    ]
    
    # Параметры поиска
    params = {
        "price_min": 30000,
        "price_max": 100000,
        "rooms": 2
    }
    
    # Progress callback
    def progress(parser_name: str, current: int, total: int):
        percentage = (current / total) * 100
        logger.info(f"[{parser_name}] Progress: {current}/{total} ({percentage:.1f}%)")
        
    # Создание процессора
    config = BatchConfig(
        max_concurrent_parsers=2,
        max_concurrent_locations=5,
        retry_failed=True
    )
    processor = BatchProcessor(config)
    
    # Запуск обработки
    logger.info("Starting batch processing...")
    results = await processor.process_multiple_parsers(
        parsers=parsers,
        locations=locations,
        params=params,
        progress_callback=progress
    )
    
    # Сохранение результатов
    processor.save_results("data/batch_results.json", results)
    
    # Вывод статистики
    stats = processor.get_stats()
    logger.info(f"Batch processing completed:")
    logger.info(f"  Total properties found: {stats['total_properties']}")
    logger.info(f"  Total errors: {stats['total_errors']}")
    

if __name__ == "__main__":
    asyncio.run(batch_parse_example())
