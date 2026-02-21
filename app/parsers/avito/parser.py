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
from app.utils.circuit_breaker import get_circuit_breaker, CircuitBreakerOpen

logger = logging.getLogger(__name__)


class AvitoParser(BaseParser):
    BASE_URL = "https://www.avito.ru"

    def __init__(self):
        super().__init__()
        self.name = "AvitoParser"

    @cached_parser(expire=600, source="avito")  # Кеш на 10 минут
    @retry(max_attempts=3, initial_delay=1.0, max_delay=10.0)
    @metrics_collector_decorator
    async def parse(self, location: str, params: Dict[str, Any] = None) -> List[PropertyCreate]:
        # Проверяем circuit breaker перед попыткой
        circuit_breaker = get_circuit_breaker("avito")
        
        try:
            return await circuit_breaker.call_async(self._parse_internal, location, params)
        except CircuitBreakerOpen as e:
            logger.warning(f"Avito parser circuit is open: {e}")
            raise NetworkError(f"Avito service temporarily unavailable: {e}")

    async def _parse_internal(self, location: str, params: Dict[str, Any]) -> List[PropertyCreate]:
        """Внутренний метод парсинга."""
        # Preprocess params
        processed_params = await self.preprocess_params(params)

        # Build URL with params
        url = f"{self.BASE_URL}/{location}/sdam/na_sutki"

        # Apply rate limiting
        await rate_limiter.acquire("avito")

        try:
            async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT) as client:
                response = await client.get(url)
                response.raise_for_status()  # Raise an exception for bad status codes
                results = self._parse_html(response.text)
                return await self.postprocess_results(results)
        except asyncio.TimeoutError as e:
            parser_error = ParserTimeoutError(f"Timeout while fetching {url}: {e}")
            ParserErrorHandler.log_error(parser_error, context="AvitoParser._parse_internal")
            raise parser_error
        except httpx.TimeoutException as e:
            parser_error = ParserTimeoutError(f"HTTP timeout: {e}")
            ParserErrorHandler.log_error(parser_error, context="AvitoParser._parse_internal")
            raise parser_error
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while fetching {url}: {e}")
            if e.response.status_code == 429:
                parser_error = RateLimitError(f"Rate limit exceeded (429)")
            elif e.response.status_code in (503, 502, 504):
                parser_error = NetworkError(f"Service unavailable ({e.response.status_code})")
            else:
                parser_error = NetworkError(f"HTTP error {e.response.status_code}: {e}")
            ParserErrorHandler.log_error(parser_error, context="AvitoParser._parse_internal")
            raise parser_error
        except httpx.RequestError as e:
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_error, context="AvitoParser.parse")
            raise parser_error
        except Exception as e:
            parser_error = ParserErrorHandler.convert_to_parser_exception(e)
            ParserErrorHandler.log_error(parser_error, context="AvitoParser.parse")
            raise parser_error

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
        from lxml import html as lxml_html
        
        tree = lxml_html.fromstring(html)
        properties = []

        for item in tree.xpath("//*[@data-marker='item']"):
            try:
                # Extract basic information using XPath (faster than CSS selectors)
                title_elem = item.xpath(".//*[@itemprop='name']")
                price_elem = item.xpath(".//*[@itemprop='price']")
                link_elem = item.xpath(".//a[@data-marker='item-title']")

                if not (title_elem and price_elem and link_elem):
                    continue

                # Parse title for rooms and area information
                title = title_elem[0].text_content().strip()
                rooms = self._extract_rooms_from_title(title)
                area = self._extract_area_from_title(title)

                # Extract photos (limit to 5 for performance)
                photos = [img.get("src") for img in item.xpath(".//img[@src]")[:5]]

                # Extract additional information
                location = self._extract_location(item)
                description = self._extract_description(item)

                # Extract link
                href = link_elem[0].get("href")
                link = self.BASE_URL + href if href else None

                props = {
                    "source": "avito",
                    "external_id": item.get("data-item-id"),
                    "title": title,
                    "price": float(price_elem[0].get("content")),
                    "link": link,
                    "rooms": rooms,
                    "area": area,
                    "photos": photos,
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

    def _extract_location(self, item) -> Optional[Dict[str, str]]:
        """Extract location information from item."""
        location = {}

        # Try to extract district/neighborhood from title
        title_elem = item.select_one("[itemprop='name']")
        if title_elem:
            title = title_elem.text.strip()
            # Look for common Moscow districts in the title
            moscow_districts = [
                "центр",
                "ц ao",
                "цао",
                "север",
                "с ao",
                "сао",
                "северо-восток",
                "св ao",
                "свао",
                "восток",
                "в ao",
                "вао",
                "юго-восток",
                "юв ao",
                "ювао",
                "юг",
                "ю ao",
                "юао",
                "юго-запад",
                "юз ao",
                "юзао",
                "запад",
                "з ao",
                "зао",
                "северо-запад",
                "сз ao",
                "сзао",
                "зеленоград",
                "таганский",
                "басманный",
                "арбат",
                "якиманка",
                "хамовники",
                "кунцево",
                "перово",
                "люблино",
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
            if len(text) > 20 and not any(keyword in text.lower() for keyword in ["руб", "м²", "комнат", "этаж"]):
                return text

        return None