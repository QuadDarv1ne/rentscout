"""
Система мониторинга для парсеров.

Отслеживает:
- Производительность парсеров
- Количество успешных/неуспешных запросов
- Средн время парсинга
- Размер кеша
- Ошибки и исключения
"""
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict
from prometheus_client import Counter, Histogram, Gauge
import json


# Prometheus метрики
parser_requests_total = Counter(
    'parser_requests_total',
    'Total number of parser requests',
    ['parser_name', 'status']
)

parser_duration_seconds = Histogram(
    'parser_duration_seconds',
    'Parser request duration in seconds',
    ['parser_name'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

parser_cache_size = Gauge(
    'parser_cache_size',
    'Current cache size',
    ['parser_name']
)

parser_properties_found = Counter(
    'parser_properties_found_total',
    'Total number of properties found',
    ['parser_name']
)


@dataclass
class ParserMetrics:
    """Метрики одного парсера."""
    parser_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_properties: int = 0
    total_duration: float = 0.0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    last_request_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Процент успешных запросов."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
        
    @property
    def cache_hit_rate(self) -> float:
        """Процент попаданий в кеш."""
        total_cache_ops = self.cache_hits + self.cache_misses
        if total_cache_ops == 0:
            return 0.0
        return (self.cache_hits / total_cache_ops) * 100
        
    @property
    def average_duration(self) -> float:
        """Среднее время запроса."""
        if self.total_requests == 0:
            return 0.0
        return self.total_duration / self.total_requests
        
    @property
    def average_properties_per_request(self) -> float:
        """Среднее количество объявлений на запрос."""
        if self.successful_requests == 0:
            return 0.0
        return self.total_properties / self.successful_requests
        
    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        data = asdict(self)
        data['success_rate'] = self.success_rate
        data['cache_hit_rate'] = self.cache_hit_rate
        data['average_duration'] = self.average_duration
        data['average_properties_per_request'] = self.average_properties_per_request
        return data


class ParserMonitor:
    """
    Монитор для отслеживания работы парсеров.
    
    Singleton класс для централизованного мониторинга.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self._metrics: Dict[str, ParserMetrics] = defaultdict(
            lambda: ParserMetrics(parser_name="unknown")
        )
        self._initialized = True
        
    def record_request(
        self,
        parser_name: str,
        duration: float,
        success: bool,
        properties_count: int = 0,
        from_cache: bool = False,
        error: Optional[Exception] = None
    ):
        """
        Записать метрики запроса.
        
        Args:
            parser_name: Название парсера
            duration: Длительность запроса в секундах
            success: Успешен ли запрос
            properties_count: Количество найденных объявлений
            from_cache: Был ли результат из кеша
            error: Исключение если произошла ошибка
        """
        metrics = self._metrics[parser_name]
        metrics.parser_name = parser_name
        metrics.total_requests += 1
        metrics.total_duration += duration
        metrics.last_request_time = datetime.now()
        
        if success:
            metrics.successful_requests += 1
            metrics.total_properties += properties_count
            parser_requests_total.labels(parser_name=parser_name, status='success').inc()
            parser_properties_found.labels(parser_name=parser_name).inc(properties_count)
        else:
            metrics.failed_requests += 1
            parser_requests_total.labels(parser_name=parser_name, status='failed').inc()
            
        if from_cache:
            metrics.cache_hits += 1
        else:
            metrics.cache_misses += 1
            
        if error:
            metrics.errors.append({
                'timestamp': datetime.now().isoformat(),
                'error_type': type(error).__name__,
                'error_message': str(error)
            })
            
        # Prometheus метрики
        parser_duration_seconds.labels(parser_name=parser_name).observe(duration)
        
    def update_cache_size(self, parser_name: str, size: int):
        """
        Обновить размер кеша.
        
        Args:
            parser_name: Название парсера
            size: Текущий размер кеша
        """
        parser_cache_size.labels(parser_name=parser_name).set(size)
        
    def get_parser_metrics(self, parser_name: str) -> Optional[ParserMetrics]:
        """
        Получить метрики конкретного парсера.
        
        Args:
            parser_name: Название парсера
            
        Returns:
            ParserMetrics или None
        """
        return self._metrics.get(parser_name)
        
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Получить метрики всех парсеров.
        
        Returns:
            Словарь с метриками всех парсеров
        """
        return {
            name: metrics.to_dict()
            for name, metrics in self._metrics.items()
        }
        
    def get_summary(self) -> Dict[str, Any]:
        """
        Получить сводную информацию по всем парсерам.
        
        Returns:
            Сводка метрик
        """
        all_metrics = list(self._metrics.values())
        
        if not all_metrics:
            return {
                'total_parsers': 0,
                'total_requests': 0,
                'overall_success_rate': 0.0,
                'total_properties': 0
            }
            
        total_requests = sum(m.total_requests for m in all_metrics)
        successful_requests = sum(m.successful_requests for m in all_metrics)
        
        return {
            'total_parsers': len(all_metrics),
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': sum(m.failed_requests for m in all_metrics),
            'overall_success_rate': (successful_requests / total_requests * 100) if total_requests > 0 else 0.0,
            'total_properties': sum(m.total_properties for m in all_metrics),
            'total_cache_hits': sum(m.cache_hits for m in all_metrics),
            'total_cache_misses': sum(m.cache_misses for m in all_metrics),
            'parsers': [m.parser_name for m in all_metrics]
        }
        
    def get_recent_errors(
        self, 
        parser_name: Optional[str] = None,
        minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Получить недавние ошибки.
        
        Args:
            parser_name: Название парсера (опционально)
            minutes: Временное окно в минутах
            
        Returns:
            Список ошибок
        """
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        errors = []
        
        metrics_to_check = [self._metrics[parser_name]] if parser_name else self._metrics.values()
        
        for metrics in metrics_to_check:
            for error in metrics.errors:
                error_time = datetime.fromisoformat(error['timestamp'])
                if error_time >= cutoff_time:
                    errors.append({
                        'parser': metrics.parser_name,
                        **error
                    })
                    
        return sorted(errors, key=lambda x: x['timestamp'], reverse=True)
        
    def export_to_json(self, filepath: str):
        """
        Экспорт метрик в JSON файл.
        
        Args:
            filepath: Путь к файлу
        """
        data = {
            'timestamp': datetime.now().isoformat(),
            'summary': self.get_summary(),
            'parsers': self.get_all_metrics()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    def reset_metrics(self, parser_name: Optional[str] = None):
        """
        Сброс метрик.
        
        Args:
            parser_name: Название парсера (опционально, если None - сбросить все)
        """
        if parser_name:
            if parser_name in self._metrics:
                del self._metrics[parser_name]
        else:
            self._metrics.clear()


# Глобальный экземпляр монитора
monitor = ParserMonitor()
