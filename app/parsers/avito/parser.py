import re
import logging
import asyncio
import httpx
from bs4 import BeautifulSoup
from app.models.schemas import PropertyCreate
from app.core.config import settings
from app.utils.ratelimiter import rate_limiter
from app.utils.error_handler import retry_on_failure, NetworkError, ParsingError
from app.parsers.base_parser import BaseParser
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class AvitoParser(BaseParser):
    BASE_URL = "https://www.avito.ru"

    def __init__(self):
        super().__init__()
        self.name = "AvitoParser"

    @retry_on_failure(
        max_retries=3, 
        base_delay=1.0,
        retry_exceptions=(httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)
    )
    async def parse(self, location: str, params: Dict[str, Any] = None) -> List[PropertyCreate]:
        # Preprocess params
        processed_params = await self.preprocess_params(params)
        
        # Build URL with params
        url = f"{self.BASE_URL}/{location}/sdam/na_sutki"
        
        # Apply rate limiting
        await rate_limiter.acquire("avito")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()  # Raise an exception for bad status codes
                results = self._parse_html(response.text)
                return await self.postprocess_results(results)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while fetching {url}: {e}")
            if e.response.status_code == 429:
                # Rate limit exceeded
                logger.warning("Rate limit exceeded, waiting before retry...")
                await asyncio.sleep(60)  # Wait for 1 minute before retry
            raise NetworkError(f"HTTP error: {e}")
        except httpx.RequestError as e:
            logger.error(f"Request error occurred while fetching {url}: {e}")
            raise NetworkError(f"Request error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error occurred while parsing {url}: {e}")
            raise ParsingError(f"Parsing error: {e}")

    async def validate_params(self, params: Dict[str, Any]) -> bool:
        """Validate Avito-specific parameters."""
        if not params:
            return True
        
        # Add validation logic for Avito-specific params here
        return True

    async def preprocess_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Preprocess parameters for Avito parser."""
        processed = await super().preprocess_params(params)
        # Add Avito-specific parameter preprocessing here
        return processed

    async def postprocess_results(self, results: List[PropertyCreate]) -> List[PropertyCreate]:
        """Postprocess results from Avito parser."""
        processed = await super().postprocess_results(results)
        # Add Avito-specific result postprocessing here
        return processed

    def _parse_html(self, html: str) -> list[PropertyCreate]:
        soup = BeautifulSoup(html, "lxml")
        properties = []
        
        for item in soup.select("[data-marker='item']"):
            try:
                # Extract basic information
                title_elem = item.select_one("[itemprop='name']")
                price_elem = item.select_one("[itemprop='price']")
                link_elem = item.select_one("a[data-marker='item-title']")
                
                if not all([title_elem, price_elem, link_elem]):
                    continue
                
                # Parse title for rooms and area information
                title = title_elem.text.strip()
                rooms = self._extract_rooms_from_title(title)
                area = self._extract_area_from_title(title)
                
                # Extract photos
                photos = []
                img_elements = item.select("img")
                for img in img_elements:
                    if img.get("src"):
                        photos.append(img["src"])
                
                # Extract additional information
                location = self._extract_location(item)
                description = self._extract_description(item)
                
                props = {
                    "source": "avito",
                    "external_id": item["data-item-id"],
                    "title": title,
                    "price": float(price_elem["content"]),
                    "link": self.BASE_URL + link_elem["href"],
                    "rooms": rooms,
                    "area": area,
                    "photos": photos[:5],  # Limit to 5 photos
                    "location": location,
                    "description": description
                }
                properties.append(PropertyCreate(**props))
            except Exception as e:
                logger.error(f"Error parsing item: {e}")
        return properties
    
    def _extract_rooms_from_title(self, title: str) -> int:
        # Look for patterns like "2-к", "2 комнатная", etc.
        room_patterns = [
            r'(\d+)[\-\s]*к',
            r'(\d+)\s*комнат',
            r'(\d+)\s*комн'
        ]
        
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
        area_patterns = [
            r'(\d+(?:[\.,]\d+)?)\s*м\s*[²2]',
            r'(\d+(?:[\.,]\d+)?)\s*кв\.?\s*м'
        ]
        
        for pattern in area_patterns:
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', '.'))
                except ValueError:
                    continue
        return None
    
    def _extract_location(self, item) -> Optional[Dict[str, str]]:
        """Extract location information from item."""
        location = {}
        
        # Try to extract district/neighborhood from title
        title_elem = item.select_one("[itemprop='name']")
        if title_elem:
            title = title_elem.text.strip()
            # Look for common Moscow districts in the title
            moscow_districts = [
                "центр", "ц ao", "цао", 
                "север", "с ao", "сао",
                "северо-восток", "св ao", "свао",
                "восток", "в ao", "вао",
                "юго-восток", "юв ao", "ювао",
                "юг", "ю ao", "юао",
                "юго-запад", "юз ao", "юзао",
                "запад", "з ao", "зао",
                "северо-запад", "сз ao", "сзао",
                "зеленоград", "таганский", "басманный",
                "арбат", "якиманка", "хамовники",
                "кунцево", "перово", "люблино"
            ]
            
            for district in moscow_districts:
                if district in title.lower():
                    location["district"] = district
                    break
        
        # Try to extract address if available
        address_elem = item.select_one("[data-marker='item-address']")
        if address_elem:
            location["address"] = address_elem.text.strip()
            
        return location if location else None
    
    def _extract_description(self, item) -> Optional[str]:
        """Extract description from item."""
        # Look for description element
        desc_elem = item.select_one("[data-marker='item-specific-params']")
        if desc_elem:
            return desc_elem.text.strip()
            
        # Alternative: look for any text content that might be a description
        content_elems = item.select("div")
        for elem in content_elems:
            text = elem.text.strip()
            # Skip if it looks like a title, price, or other structured data
            if (len(text) > 20 and 
                not any(keyword in text.lower() for keyword in ["руб", "м²", "комнат", "этаж"])):
                return text
                
        return None