"""
Парсер для Etagi.com - крупный портал недвижимости.

Парсит:
- Аренда квартир (длительная)
- Аренда посуточно
- Продажа

URL: https://etagi.com/
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


class EtagiParser(OptimizedBaseParser):
    """
    Парсер для Etagi.com.
    
    Особенности:
    - Использует антибот-обход через ротацию User-Agent
    - Парсинг через BeautifulSoup
    - Поддержка пагинации
    """

    def __init__(self):
        super().__init__(ParserConfig(
            name="EtagiParser",
            base_url="https://etagi.com",
            timeout=30,
            max_retries=3,
            rate_limit=1,  # 1 запрос в секунду
            max_concurrent=2,
            cache_ttl=600,  # 10 минут
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "keep-alive",
            }
        ))

    async def _parse_impl(self, location: str, params: Dict[str, Any]) -> List[PropertyCreate]:
        """
        Парсинг объявлений для локации.
        
        Args:
            location: Город для поиска
            params: Параметры поиска (rooms, price и т.д.)
            
        Returns:
            Список PropertyCreate
        """
        results: List[PropertyCreate] = []
        
        # Формируем URL для поиска
        search_url = self._build_search_url(location, params)
        
        try:
            async with EnhancedHTTPClient(
                timeout=self.config.timeout,
                headers=self.config.headers
            ) as client:
                # Получаем первую страницу
                response = await client.get(search_url)
                
                if response.status_code != 200:
                    logger.warning(f"Etagi parser: non-200 status {response.status_code}")
                    return results
                
                # Парсим HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Находим все объявления на странице
                listings = soup.find_all('div', class_='listing-item')
                
                if not listings:
                    # Пробуем альтернативный селектор
                    listings = soup.find_all('article', class_='card')
                
                for listing in listings:
                    try:
                        property_data = self._parse_listing(listing, location)
                        if property_data:
                            results.append(property_data)
                    except Exception as e:
                        logger.error(f"Error parsing listing: {e}")
                        continue
                
                # Пагинация - получаем следующие страницы (опционально)
                # max_pages можно передать в params
                max_pages = params.get('max_pages', 3)
                for page in range(2, min(max_pages + 1, 6)):  # Максимум 5 страниц
                    next_url = f"{search_url}&page={page}"
                    try:
                        response = await client.get(next_url)
                        if response.status_code != 200:
                            break
                        
                        soup = BeautifulSoup(response.text, 'html.parser')
                        listings = soup.find_all('div', class_='listing-item')
                        
                        for listing in listings:
                            property_data = self._parse_listing(listing, location)
                            if property_data:
                                results.append(property_data)
                    except Exception as e:
                        logger.error(f"Error on page {page}: {e}")
                        break
                
        except Exception as e:
            logger.error(f"Etagi parser error: {e}")
        
        logger.info(f"Etagi parser: found {len(results)} properties for {location}")
        return results

    def _build_search_url(self, location: str, params: Dict[str, Any]) -> str:
        """
        Построение URL для поиска.
        
        Пример: https://etagi.com/arenda/kvartiry/msk/?rooms=2&price_max=50000
        """
        base_url = f"{self.config.base_url}/arenda/kvartiry/"
        
        # Маппинг городов
        city_mapping = {
            "москва": "msk",
            "санкт-петербург": "spb",
            "екатеринбург": "ekb",
            "казань": "kzn",
            "нижний новгород": "nnov",
        }
        
        city_slug = city_mapping.get(location.lower(), location.lower().replace(" ", "-"))
        url = f"{base_url}{city_slug}/?"
        
        # Добавляем параметры
        query_params = []
        
        if 'rooms' in params:
            rooms = params['rooms']
            if isinstance(rooms, int):
                query_params.append(f"rooms={rooms}")
            elif isinstance(rooms, str) and '-' in rooms:
                # Диапазон комнат
                query_params.append(f"rooms[]={rooms.split('-')[0]}&rooms[]={rooms.split('-')[1]}")
        
        if 'min_price' in params:
            query_params.append(f"price_min={int(params['min_price'])}")
        
        if 'max_price' in params:
            query_params.append(f"price_max={int(params['max_price'])}")
        
        if 'min_area' in params:
            query_params.append(f"area_min={int(params['min_area'])}")
        
        if 'max_area' in params:
            query_params.append(f"area_max={int(params['max_area'])}")
        
        # Сортировка по дате (сначала новые)
        query_params.append("sort=date_desc")
        
        return url + "&".join(query_params)

    def _parse_listing(self, listing, location: str) -> Optional[PropertyCreate]:
        """
        Парсинг отдельного объявления.
        
        Args:
            listing: BeautifulSoup элемент объявления
            location: Город
            
        Returns:
            PropertyCreate или None
        """
        try:
            # Извлекаем данные
            title_elem = listing.find('a', class_='listing-title')
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            link = title_elem.get('href', '')
            if link and not link.startswith('http'):
                link = f"{self.config.base_url}{link}"
            
            # Цена
            price_elem = listing.find('div', class_='listing-price')
            price = 0
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # Очищаем от символов валюты и пробелов
                price_str = ''.join(filter(str.isdigit, price_text))
                if price_str:
                    price = int(price_str)
            
            # Комнаты, площадь, этаж
            params_elem = listing.find('div', class_='listing-params')
            rooms = None
            area = None
            floor = None
            total_floors = None
            
            if params_elem:
                param_items = params_elem.find_all('div', class_='param-item')
                for item in param_items:
                    param_name = item.get('data-param', '')
                    param_value = item.get_text(strip=True)
                    
                    if 'rooms' in param_name.lower():
                        rooms = int(''.join(filter(str.isdigit, param_value))) if param_value else None
                    elif 'area' in param_name.lower():
                        area_str = ''.join(filter(lambda c: c.isdigit() or c == '.', param_value))
                        area = float(area_str) if area_str else None
                    elif 'floor' in param_name.lower():
                        floor_parts = param_value.split('/')
                        if len(floor_parts) >= 2:
                            floor = int(floor_parts[0].strip())
                            total_floors = int(floor_parts[1].strip())
            
            # Фотографии
            photos = []
            img_elem = listing.find('img', class_='listing-image')
            if img_elem:
                img_src = img_elem.get('src') or img_elem.get('data-src')
                if img_src:
                    photos.append(img_src if img_src.startswith('http') else f"{self.config.base_url}{img_src}")
            
            # Описание (если есть на странице списка)
            description_elem = listing.find('div', class_='listing-description')
            description = description_elem.get_text(strip=True) if description_elem else None
            
            # Адрес/район
            address_elem = listing.find('div', class_='listing-address')
            address = address_elem.get_text(strip=True) if address_elem else None
            
            return PropertyCreate(
                source="etagi",
                external_id=self._extract_external_id(link),
                title=title,
                description=description,
                link=link,
                price=price,
                rooms=rooms,
                area=area,
                floor=floor,
                total_floors=total_floors,
                city=location,
                address=address,
                photos=photos,
                is_active=True,
                is_verified=False,
            )
            
        except Exception as e:
            logger.error(f"Error parsing listing element: {e}")
            return None

    def _extract_external_id(self, url: str) -> str:
        """Извлекает ID объявления из URL."""
        # Пример URL: https://etagi.com/arenda/kvartiry/12345/
        parts = url.rstrip('/').split('/')
        return parts[-1] if parts else url

    async def parse_property_details(self, property_url: str) -> Optional[Dict[str, Any]]:
        """
        Парсинг детальной информации об объявлении.
        
        Args:
            property_url: URL объявления
            
        Returns:
            Dict с дополнительной информацией
        """
        try:
            async with EnhancedHTTPClient(
                timeout=self.config.timeout,
                headers=self.config.headers
            ) as client:
                response = await client.get(property_url)
                
                if response.status_code != 200:
                    return None
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                details = {}
                
                # Полное описание
                desc_elem = soup.find('div', class_='property-description')
                if desc_elem:
                    details['full_description'] = desc_elem.get_text(strip=True)
                
                # Все фотографии
                photos = []
                photo_elems = soup.find_all('img', class_='property-photo')
                for photo in photo_elems:
                    src = photo.get('src') or photo.get('data-src')
                    if src:
                        photos.append(src if src.startswith('http') else f"{self.config.base_url}{src}")
                details['all_photos'] = photos
                
                # Контактная информация
                contact_elem = soup.find('div', class_='contact-info')
                if contact_elem:
                    phone_elem = contact_elem.find('span', class_='phone')
                    if phone_elem:
                        details['phone'] = phone_elem.get_text(strip=True)
                    
                    name_elem = contact_elem.find('div', class_='agent-name')
                    if name_elem:
                        details['agent_name'] = name_elem.get_text(strip=True)
                
                # Характеристики
                features = {}
                feature_elems = soup.find_all('div', class_='feature-item')
                for feature in feature_elems:
                    key_elem = feature.find('span', class_='feature-key')
                    value_elem = feature.find('span', class_='feature-value')
                    if key_elem and value_elem:
                        features[key_elem.get_text(strip=True)] = value_elem.get_text(strip=True)
                details['features'] = features
                
                return details
                
        except Exception as e:
            logger.error(f"Error parsing property details: {e}")
            return None


# Фабричная функция для создания парсера
def create_etagi_parser() -> EtagiParser:
    """Создаёт экземпляр парсера Etagi."""
    return EtagiParser()
