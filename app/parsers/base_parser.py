from abc import ABC, abstractmethod

import functools
import time
from typing import Any, Dict, List

from app.models.schemas import PropertyCreate
from app.utils.metrics import metrics_collector
from app.utils.parser_errors import ErrorClassifier


class BaseParser(ABC):
    """Абстрактный базовый класс для всех парсеров."""

    def __init__(self):
        self.name = self.__class__.__name__

    @abstractmethod
    async def parse(self, location: str, params: Dict[str, Any] = None) -> List[PropertyCreate]:
        """
        Абстрактный метод для парсинга данных.

        Args:
            location: Город или местоположение для поиска
            params: Дополнительные параметры поиска

        Returns:
            Список объектов PropertyCreate с информацией о недвижимости
        """
        pass

    @abstractmethod
    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Абстрактный метод для валидации параметров.

        Args:
            params: Параметры для валидации

        Returns:
            True если параметры валидны, иначе False
        """
        pass

    async def preprocess_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Метод для предобработки параметров перед парсингом.
        Может быть переопределен в подклассах.

        Args:
            params: Исходные параметры

        Returns:
            Обработанные параметры
        """
        return params or {}

    async def postprocess_results(self, results: List[PropertyCreate]) -> List[PropertyCreate]:
        """
        Метод для постобработки результатов после парсинга.
        Может быть переопределен в подклассах.

        Args:
            results: Список спарсенных объектов

        Returns:
            Обработанный список объектов
        """
        # Record metrics for processed properties
        for result in results:
            metrics_collector.record_property_processed(result.source, "parsed")
        
        return results


def metrics_collector_decorator(func):
    """
    Декоратор для автоматического сбора метрик выполнения парсеров.
    """
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        start_time = time.time()
        parser_name = self.__class__.__name__

        try:
            result = await func(self, *args, **kwargs)
            duration = time.time() - start_time
            metrics_collector.record_parser_call(parser_name, "success", duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            # Classify the error to get error type for metrics
            classification = ErrorClassifier.classify(e)
            error_type = classification.get("type", "UnknownError")
            metrics_collector.record_parser_call(parser_name, "error", duration, error_type)
            raise

    return wrapper