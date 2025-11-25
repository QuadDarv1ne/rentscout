import re
import logging
import httpx
from bs4 import BeautifulSoup
from app.models.schemas import PropertyCreate
from app.core.config import settings
from tenacity import retry, stop_after_attempt

logger = logging.getLogger(__name__)

class AvitoParser:
    BASE_URL = "https://www.avito.ru"

    @retry(stop=stop_after_attempt(3))
    async def parse_listing(self, city: str) -> list[PropertyCreate]:
        url = f"{self.BASE_URL}/{city}/sdam/na_sutki"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()  # Raise an exception for bad status codes
                return self._parse_html(response.text)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while fetching {url}: {e}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error occurred while fetching {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error occurred while parsing {url}: {e}")
            raise

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
                
                props = {
                    "source": "avito",
                    "external_id": item["data-item-id"],
                    "title": title,
                    "price": float(price_elem["content"]),
                    "link": self.BASE_URL + link_elem["href"],
                    "rooms": rooms,
                    "area": area,
                    "photos": photos[:5]  # Limit to 5 photos
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
