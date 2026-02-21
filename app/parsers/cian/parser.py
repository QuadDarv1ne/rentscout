import asyncio
import httpx
import logging
import re
from bs4 import BeautifulSoup
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.schemas import PropertyCreate
from app.parsers.base_parser import BaseParser, metrics_collector_decorator
from app.services.advanced_cache import cached_parser
from app.utils.parser_errors import (
    ParserErrorHandler,
    RateLimitError,
    TimeoutError as ParserTimeoutError,
    NetworkError,
    ParsingError,
    ErrorClassifier,
)
from app.utils.retry import retry
from app.utils.ratelimiter import rate_limiter

logger = logging.getLogger(__name__)


class CianParser(BaseParser):
    BASE_URL = "https://www.cian.ru"
    
    def __init__(self):
        super().__init__()
        self.name = "CianParser"
        
    @cached_parser(expire=600, source="cian")  # Кеш на 10 минут
    @retry(max_attempts=3, initial_delay=1.0, max_delay=10.0)
    @metrics_collector_decorator
    async def parse(self, location: str, params: Dict[str, Any] = None) -> List[PropertyCreate]:
        # Preprocess params
        processed_params = await self.preprocess_params(params)
        
        # Build URL with params
        url = f"{self.BASE_URL}/cat.php"
        query_params = self._build_query_params(location, processed_params)
        
        # Apply rate limiting
        await rate_limiter.acquire("cian")
        
        try:
            # Используем оптимизированный HTTP клиент из пула
            from app.utils.http_pool import OptimizedHTTPClient
            
            async with OptimizedHTTPClient(name="cian") as client:
                response = await client.get(url, params=query_params)
                results = self._parse_html(response.text)
                return await self.postprocess_results(results)
                
        except asyncio.TimeoutError as e:
            parser_error = ParserTimeoutError(f"Timeout while fetching {url}: {e}")
            ParserErrorHandler.log_error(parser_error, context="CianParser.parse")
            raise parser_error
        except httpx.TimeoutException as e:
            parser_error = ParserTimeoutError(f"HTTP timeout: {e}")
            ParserErrorHandler.log_error(parser_error, context="CianParser.parse")
            raise parser_error
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while fetching {url}: {e}")
            if e.response.status_code == 429:
                parser_error = RateLimitError(f"Rate limit exceeded (429)")
            elif e.response.status_code in (503, 502, 504):
                parser_error = NetworkError(f"Service unavailable ({e.response.status_code})")
            else:
                parser_error = NetworkError(f"HTTP error {e.response.status_code}: {e}")
            ParserErrorHandler.log_error(parser_error, context="CianParser.parse")
            raise parser_error
        except httpx.RequestError as e:
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_error, context="CianParser.parse")
            raise parser_error
        except Exception as e:
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_error, context="CianParser.parse")
            raise parser_error
            
    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate Cian-specific parameters."""
        if not params:
            return True
            
        # Add validation logic for Cian-specific params here
        return True
        
    async def preprocess_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess parameters for Cian parser."""
        processed = await super().preprocess_params(params)
        # Add Cian-specific parameter preprocessing here
        return processed
        
    async def postprocess_results(self, results: List[PropertyCreate]) -> List[PropertyCreate]:
        """Postprocess results from Cian parser."""
        processed = await super().postprocess_results(results)
        # Add Cian-specific result postprocessing here
        return processed
        
    def _build_query_params(self, location: str, params: Dict[str, Any]) -> Dict[str, str]:
        """Build query parameters for Cian search."""
        query_params = {
            "engine_version": "2",
            "offer_type": "rent",
            "type": "4",  # Квартиры
            "currency": "2",  # RUB
            "deal_type": "rent",
            "region": "1",  # Москва (по умолчанию)
        }
        
        # Map location to region code if needed
        # In a real implementation, this would map city names to CIAN region IDs
        if location.lower() in ["москва", "moscow"]:
            query_params["region"] = "1"
        elif location.lower() in ["санкт-петербург", "spb", "saint petersburg"]:
            query_params["region"] = "2"
            
        # Add property type filter
        if params and "type" in params:
            property_type = params["type"].lower()
            if property_type == "квартира":
                query_params["type"] = "4"
            elif property_type == "комната":
                query_params["type"] = "5"
            elif property_type == "дом":
                query_params["type"] = "3"
                
        # Add price filters
        if params and "min_price" in params and params["min_price"]:
            query_params["price_min"] = str(int(params["min_price"]))
            
        if params and "max_price" in params and params["max_price"]:
            query_params["price_max"] = str(int(params["max_price"]))
            
        # Add room count filter
        if params and "rooms" in params and params["rooms"]:
            rooms = params["rooms"]
            if isinstance(rooms, int):
                query_params["room"] = str(rooms)
            elif isinstance(rooms, list):
                # Handle multiple room options
                room_params = []
                for room in rooms:
                    if isinstance(room, int) and 1 <= room <= 5:
                        room_params.append(f"room{room}")
                if room_params:
                    query_params.update({rp: "1" for rp in room_params})
                        
        return query_params
        
    def _parse_html(self, html: str) -> list[PropertyCreate]:
        soup = BeautifulSoup(html, "lxml")
        properties = []
        
        # Find property listings
        # Note: Actual selectors would need to be updated based on CIAN's current HTML structure
        listings = soup.select("[data-name='CardComponent']")
        
        for item in listings:
            try:
                # Extract basic information
                title_elem = item.select_one("[data-name='Title']")
                price_elem = item.select_one("[data-name='Price']") or item.select_one("[data-mark='MainPrice']")
                
                if not all([title_elem, price_elem]):
                    continue
                    
                # Extract title
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                # Extract price (remove non-numeric characters except decimal point)
                price_text = price_elem.get_text(strip=True) if price_elem else ""
                price_digits = re.findall(r'[\d\s]+', price_text)
                price = float(''.join(price_digits).replace(' ', '')) if price_digits else 0
                
                # Extract link
                link_elem = item.select_one("a")
                link = link_elem.get("href", "") if link_elem else ""
                if link and not link.startswith("http"):
                    link = self.BASE_URL + link
                    
                # Parse title for rooms and area information
                rooms = self._extract_rooms_from_title(title)
                area = self._extract_area_from_title(title)
                
                # Extract photos
                photos = []
                img_elements = item.select("img")
                for img in img_elements:
                    if img.get("src"):
                        photos.append(img["src"])
                        
                # Extract additional information
                location = self._extract_location(item, title)
                description = self._extract_description(item)
                
                props = {
                    "source": "cian",
                    "external_id": self._extract_external_id(link),
                    "title": title,
                    "price": price,
                    "link": link,
                    "rooms": rooms,
                    "area": area,
                    "photos": photos[:5],  # Limit to 5 photos
                    "location": location,
                    "description": description,
                }
                properties.append(PropertyCreate(**props))
            except Exception as e:
                logger.error(f"Error parsing item: {e}")
                
        return properties
        
    def _extract_rooms_from_title(self, title: str) -> int:
        # Look for patterns like "2-к", "2 комнатная", etc.
        room_patterns = [r'(\d+)[\-\s]*к', r'(\d+)\s*комнат', r'(\d+)\s*комн']
        
        for pattern in room_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        return None
        
    def _extract_area_from_title(self, title: str) -> float:
        # Look for patterns like "45 м²", "50м2", etc.
        area_patterns = [r'(\d+(?:[\.,]\d+)?)\s*м\s*[²2]', r'(\d+(?:[\.,]\d+)?)\s*кв\.?\s*м']
        
        for pattern in area_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except ValueError:
                    continue
        return None
        
    def _extract_location(self, item, title: str = "") -> Optional[Dict[str, str]]:
        """Extract location information from item."""
        location = {}
        
        # Try to extract district/neighborhood from title
        if title:
            # Look for common Moscow districts in the title
            moscow_districts = [
                "центр", "цао", "север", "сао", "северо-восток", "свао", "восток", "вао",
                "юго-восток", "ювао", "юг", "юао", "юго-запад", "юзао", "запад", "зао",
                "северо-запад", "сзао", "зеленоград", "таганский", "басманный", "арбат",
                "якиманка", "хамовники", "кунцево", "перово", "люблино"
            ]
            
            for district in moscow_districts:
                if district in title.lower():
                    location["district"] = district
                    break
                    
        # Try to extract address if available
        address_elem = item.select_one("[data-name='AddressLine']") or item.select_one("[data-mark='Address']")
        if address_elem:
            location["address"] = address_elem.get_text(strip=True)
            
        return location if location else None
        
    def _extract_description(self, item) -> Optional[str]:
        """Extract description from item."""
        # Look for description element
        desc_elem = item.select_one("[data-name='Description']") or item.select_one("[data-mark='Description']")
        if desc_elem:
            return desc_elem.get_text(strip=True)
            
        return None
        
    def _extract_external_id(self, link: str) -> str:
        """Extract external ID from link."""
        # Extract ID from URL like https://www.cian.ru/rent/flat/123456789/
        match = re.search(r'/(\d+)/?$', link)
        return match.group(1) if match else ""