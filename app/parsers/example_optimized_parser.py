"""
Пример реализации парсера на основе OptimizedBaseParser.
"""
from typing import Any, Dict, List
from bs4 import BeautifulSoup

from app.parsers.optimized_base_parser import OptimizedBaseParser, ParserConfig
from app.models.schemas import PropertyCreate


class ExampleOptimizedParser(OptimizedBaseParser):
    """
    Пример оптимизированного парсера.
    
    Демонстрирует использование базового класса с:
    - Connection pooling
    - Rate limiting
    - Caching
    - Performance monitoring
    """
    
    def __init__(self):
        """Инициализация парсера с конфигурацией."""
        config = ParserConfig(
            name="ExampleParser",
            base_url="https://example.com",
            timeout=30,
            max_retries=3,
            rate_limit=10,
            max_concurrent=5,
            cache_ttl=300
        )
        super().__init__(config)
        
    async def _parse_impl(
        self, 
        location: str, 
        params: Dict[str, Any]
    ) -> List[PropertyCreate]:
        """
        Реализация парсинга.
        
        Args:
            location: Город
            params: Параметры поиска
            
        Returns:
            Список объектов недвижимости
        """
        # Формирование URL
        url = f"/search?city={location}"
        if params.get("price_min"):
            url += f"&price_min={params['price_min']}"
        if params.get("price_max"):
            url += f"&price_max={params['price_max']}"
            
        # Выполнение запроса через оптимизированный метод
        response = await self._make_request("GET", url)
        
        # Парсинг HTML
        soup = BeautifulSoup(response.text, 'lxml')
        listings = soup.find_all('div', class_='listing')
        
        results = []
        for listing in listings:
            try:
                property_data = self._parse_listing(listing)
                results.append(property_data)
            except Exception as e:
                # Логирование ошибки парсинга конкретного объявления
                print(f"Error parsing listing: {e}")
                continue
                
        return results
        
    def _parse_listing(self, listing) -> PropertyCreate:
        """
        Парсинг одного объявления.
        
        Args:
            listing: BeautifulSoup element с объявлением
            
        Returns:
            PropertyCreate object
        """
        title = listing.find('h2', class_='title').text.strip()
        price_text = listing.find('span', class_='price').text
        price = float(price_text.replace(' ', '').replace('₽', ''))
        
        address = listing.find('div', class_='address').text.strip()
        rooms = int(listing.find('span', class_='rooms').text)
        area = float(listing.find('span', class_='area').text.replace(' м²', ''))
        
        return PropertyCreate(
            title=title,
            price=price,
            address=address,
            rooms=rooms,
            area=area,
            source=self.name
        )
        
    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Валидация параметров поиска.
        
        Args:
            params: Параметры для валидации
            
        Returns:
            True если параметры валидны
        """
        if "price_min" in params and "price_max" in params:
            if params["price_min"] > params["price_max"]:
                return False
                
        if "rooms" in params:
            if not isinstance(params["rooms"], int) or params["rooms"] < 0:
                return False
                
        return True
        
    async def preprocess_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Предобработка параметров.
        
        Args:
            params: Исходные параметры
            
        Returns:
            Обработанные параметры
        """
        processed = params.copy()
        
        # Установка значений по умолчанию
        processed.setdefault("price_min", 0)
        processed.setdefault("price_max", 1000000000)
        
        # Нормализация значений
        if "rooms" in processed:
            processed["rooms"] = max(0, int(processed["rooms"]))
            
        return processed


# Пример использования
async def example_usage():
    """Демонстрация использования оптимизированного парсера."""
    
    # Создание парсера
    async with ExampleOptimizedParser() as parser:
        # Одиночный парсинг
        results = await parser.parse(
            location="Москва",
            params={"price_min": 50000, "price_max": 100000, "rooms": 2}
        )
        print(f"Found {len(results)} properties")
        
        # Пакетный парсинг нескольких городов
        locations = ["Москва", "Санкт-Петербург", "Казань"]
        batch_results = await parser.batch_parse(
            locations=locations,
            params={"price_min": 30000, "rooms": 1}
        )
        
        for city, properties in batch_results.items():
            print(f"{city}: {len(properties)} properties")
            
        # Получение статистики
        stats = parser.get_stats()
        print(f"Parser stats: {stats}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
