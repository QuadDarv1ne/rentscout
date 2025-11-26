from abc import ABC, abstractmethod
from typing import List, Dict, Any
from app.models.schemas import PropertyCreate

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
        return results