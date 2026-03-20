"""
Парсер для Cian.ru - раздел коммерческой недвижимости.

Парсит:
- Офисные помещения
- Торговые помещения
- Склады
- Производственные помещения
- Земельные участки

URL: https://www.cian.ru/kommercheskaya-nedvizhimost/
"""

import asyncio
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.models.schemas import PropertyCreate
from app.parsers.optimized_base_parser import OptimizedBaseParser, ParserConfig
from app.utils.logger import logger
from app.utils.enhanced_http import EnhancedHTTPClient


class CianCommercialParser(OptimizedBaseParser):
    """
    Парсер для Cian.ru Commercial.
    
    Особенности:
    - Парсинг коммерческой недвижимости
    - Поддержка различных типов помещений
    - Обход базовой защиты через ротацию User-Agent
    """

    def __init__(self):
        super().__init__(ParserConfig(
            name="CianCommercialParser",
            base_url="https://www.cian.ru",
            timeout=30,
            max_retries=3,
            rate_limit=0.5,  # 1 запрос в 2 секунды
            max_concurrent=2,
            cache_ttl=900,  # 15 минут
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        ))

    async def _parse_impl(self, location: str, params: Dict[str, Any]) -> List[PropertyCreate]:
        """
        Парсинг коммерческой недвижимости для локации.
        
        Args:
            location: Город для поиска
            params: Параметры поиска (property_type, price, area и т.д.)
            
        Returns:
            Список PropertyCreate
        """
        results: List[PropertyCreate] = []
        
        # Определяем тип коммерческой недвижимости
        property_type = params.get('property_type', 'office')
        category_url = self._get_category_url(property_type, location)
        
        try:
            async with EnhancedHTTPClient(
                timeout=self.config.timeout,
                headers=self.config.headers
            ) as client:
                # Получаем первую страницу
                response = await client.get(category_url)
                
                if response.status_code != 200:
                    logger.warning(f"Cian Commercial parser: non-200 status {response.status_code}")
                    # Cian может возвращать 403 при блокировке
                    if response.status_code == 403:
                        logger.error("Cian Commercial: possible bot detection (403)")
                    return results
                
                # Парсим HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Находим все объявления на странице
                # Cian использует динамическую загрузку, парсим initial data
                listings = self._parse_listings_from_script(soup, location)
                
                if listings:
                    results.extend(listings)
                
                # Пагинация (опционально)
                max_pages = params.get('max_pages', 2)
                for page in range(2, min(max_pages + 1, 4)):  # Максимум 3 страницы
                    next_url = f"{category_url}&p={page}"
                    try:
                        response = await client.get(next_url)
                        if response.status_code != 200:
                            break
                        
                        soup = BeautifulSoup(response.text, 'html.parser')
                        page_listings = self._parse_listings_from_script(soup, location)
                        
                        if page_listings:
                            results.extend(page_listings)
                        else:
                            break
                    except Exception as e:
                        logger.error(f"Error on page {page}: {e}")
                        break
                
        except Exception as e:
            logger.error(f"Cian Commercial parser error: {e}")
        
        logger.info(f"Cian Commercial parser: found {len(results)} properties for {location}")
        return results

    def _get_category_url(self, property_type: str, location: str) -> str:
        """
        Построение URL для категории коммерческой недвижимости.
        
        Args:
            property_type: Тип недвижимости (office, retail, warehouse, etc.)
            location: Город
            
        Returns:
            URL для поиска
        """
        # Маппинг типов недвижимости в URL Cian
        type_mapping = {
            "office": "ofisnye-pomescheniya",
            "retail": "torgovye-pomescheniya",
            "warehouse": "skladskie-pomescheniya",
            "production": "proizvodstvennye-pomescheniya",
            "land": "zemelnye-uchastki",
            "building": "zdaniya",
        }
        
        # Маппинг городов
        city_mapping = {
            "москва": "moskva",
            "санкт-петербург": "sankt-peterburg",
            "екатеринбург": "ekaterinburg",
            "казань": "kazan",
            "нижний новгород": "nizhniy-novgorod",
        }
        
        city_slug = city_mapping.get(location.lower(), location.lower().replace(" ", "-"))
        type_slug = type_mapping.get(property_type.lower(), "ofisnye-pomescheniya")
        
        # Формируем URL
        base_url = f"{self.config.base_url}/kommmercheskaya-nedvizhimost/arenda/{type_slug}/{city_slug}/"
        
        # Добавляем параметры (можно расширить)
        return base_url

    def _parse_listings_from_script(self, soup: BeautifulSoup, location: str) -> List[PropertyCreate]:
        """
        Парсинг объявлений из JSON-LD или script данных Cian.
        
        Cian часто использует динамическую загрузку через JavaScript,
        поэтому данные могут быть в script тегах.
        
        Args:
            soup: BeautifulSoup объект
            location: Город
            
        Returns:
            Список PropertyCreate
        """
        results = []
        
        # Пробуем найти JSON-LD данные
        script_tags = soup.find_all('script', type='application/ld+json')
        
        for script in script_tags:
            try:
                import json
                data = json.loads(script.string)
                
                # Обработка различных форматов
                if isinstance(data, list):
                    for item in data:
                        property_data = self._parse_json_ld_item(item, location)
                        if property_data:
                            results.append(property_data)
                elif isinstance(data, dict):
                    if '@graph' in data:
                        for item in data['@graph']:
                            property_data = self._parse_json_ld_item(item, location)
                            if property_data:
                                results.append(property_data)
                    else:
                        property_data = self._parse_json_ld_item(data, location)
                        if property_data:
                            results.append(property_data)
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.debug(f"Error parsing JSON-LD: {e}")
                continue
        
        # Если не нашли в JSON-LD, пробуем обычный HTML парсинг
        if not results:
            results = self._parse_listings_html(soup, location)
        
        return results

    def _parse_json_ld_item(self, item: dict, location: str) -> Optional[PropertyCreate]:
        """
        Парсинг элемента JSON-LD.
        
        Args:
            item: JSON-LD объект
            location: Город
            
        Returns:
            PropertyCreate или None
        """
        try:
            # Проверяем тип
            if item.get('@type') not in ['Product', 'Offer', 'RealEstateListing']:
                return None
            
            # Извлекаем данные
            title = item.get('name', '')
            if not title:
                return None
            
            # Цена
            price = 0
            if 'offers' in item:
                offers = item['offers']
                if isinstance(offers, dict):
                    price = float(offers.get('price', 0))
                elif isinstance(offers, list) and offers:
                    price = float(offers[0].get('price', 0))
            
            # URL
            url = item.get('url', '')
            
            # Описание
            description = item.get('description', '')
            
            # Изображения
            photos = []
            if 'image' in item:
                if isinstance(item['image'], list):
                    photos = item['image'][:5]  # Берём первые 5
                elif isinstance(item['image'], str):
                    photos = [item['image']]
            
            # Адрес
            address = ''
            if 'address' in item:
                addr = item['address']
                if isinstance(addr, dict):
                    address = addr.get('streetAddress', '')
                    city = addr.get('addressLocality', '')
                    if city:
                        location = city
                elif isinstance(addr, str):
                    address = addr
            
            # Площадь (если есть в additionalProperty)
            area = None
            rooms = None
            if 'additionalProperty' in item:
                for prop in item['additionalProperty']:
                    if isinstance(prop, dict):
                        name = prop.get('name', '').lower()
                        value = prop.get('value')
                        if value:
                            if 'площадь' in name.lower():
                                try:
                                    area = float(value)
                                except (ValueError, TypeError):
                                    pass
                            elif 'комнат' in name.lower() or 'rooms' in name.lower():
                                try:
                                    rooms = int(value)
                                except (ValueError, TypeError):
                                    pass
            
            return PropertyCreate(
                source="cian_commercial",
                external_id=self._extract_external_id(url),
                title=title,
                description=description,
                link=url,
                price=price,
                rooms=rooms,
                area=area,
                city=location,
                address=address,
                photos=photos,
                is_active=True,
                is_verified=False,
            )
            
        except Exception as e:
            logger.debug(f"Error parsing JSON-LD item: {e}")
            return None

    def _parse_listings_html(self, soup: BeautifulSoup, location: str) -> List[PropertyCreate]:
        """
        Резервный метод парсинга через HTML.
        
        Args:
            soup: BeautifulSoup объект
            location: Город
            
        Returns:
            Список PropertyCreate
        """
        results = []
        
        # Ищем карточки объявлений
        # Cian использует различные классы, пробуем несколько вариантов
        listing_containers = soup.find_all('div', {'data-name': 'ListingItem'})
        
        if not listing_containers:
            listing_containers = soup.find_all('div', class_='_9344497d00')
        
        for listing in listing_containers:
            try:
                property_data = self._parse_html_listing(listing, location)
                if property_data:
                    results.append(property_data)
            except Exception as e:
                logger.debug(f"Error parsing HTML listing: {e}")
                continue
        
        return results

    def _parse_html_listing(self, listing, location: str) -> Optional[PropertyCreate]:
        """
        Парсинг отдельного объявления из HTML.
        
        Args:
            listing: BeautifulSoup элемент
            location: Город
            
        Returns:
            PropertyCreate или None
        """
        try:
            # Заголовок
            title_elem = listing.find('a', class_='_9344497d00')
            if not title_elem:
                title_elem = listing.find('a', href=True)
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            link = title_elem.get('href', '')
            if link and not link.startswith('http'):
                link = f"{self.config.base_url}{link}"
            
            # Цена
            price_elem = listing.find('div', class_='_9344497d01')
            price = 0
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                price_str = ''.join(filter(str.isdigit, price_text))
                if price_str:
                    price = int(price_str)
            
            # Площадь и параметры
            params_elem = listing.find('div', class_='_9344497d02')
            area = None
            rooms = None
            
            if params_elem:
                params_text = params_elem.get_text(strip=True)
                # Парсинг строки вида "100 м² • 1 этаж из 5"
                import re
                area_match = re.search(r'(\d+(?:\.\d+)?)\s*м²', params_text)
                if area_match:
                    area = float(area_match.group(1))
            
            # Фото
            photos = []
            img_elem = listing.find('img')
            if img_elem:
                img_src = img_elem.get('src') or img_elem.get('data-src')
                if img_src:
                    photos.append(img_src if img_src.startswith('http') else f"https:{img_src}")
            
            return PropertyCreate(
                source="cian_commercial",
                external_id=self._extract_external_id(link),
                title=title,
                description=None,
                link=link,
                price=price,
                rooms=rooms,
                area=area,
                city=location,
                address=None,
                photos=photos,
                is_active=True,
                is_verified=False,
            )
            
        except Exception as e:
            logger.debug(f"Error parsing HTML listing element: {e}")
            return None

    def _extract_external_id(self, url: str) -> str:
        """Извлекает ID объявления из URL."""
        # Пример URL: https://www.cian.ru/snyat-kommercheskoe-pomeschenie-12345678/
        import re
        match = re.search(r'-(\d+)/', url)
        return match.group(1) if match else url


# Фабричная функция
def create_cian_commercial_parser() -> CianCommercialParser:
    """Создаёт экземпляр парсера Cian Commercial."""
    return CianCommercialParser()
