import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import httpx

from app.models.schemas import PropertyCreate
from app.parsers.optimized_base_parser import OptimizedBaseParser, ParserConfig
from app.utils.enhanced_http import EnhancedHTTPClient
from app.utils.logger import logger


@dataclass
class OpenSource:
    name: str
    url: str
    parser: str  # 'json' | 'rss' | 'csv'
    location_field: Optional[str] = None


class OpenDataParser(OptimizedBaseParser):
    """
    Парсер открытых источников (публичные API, RSS, CSV).
    Без агрессивных антибот-защит, с дружелюбными rate limits.
    """

    def __init__(self):
        sources: List[OpenSource] = [
            # Примеры открытых источников (замените на реальные в бою)
            OpenSource(
                name="Open-Municipal-Feed",
                url="https://raw.githubusercontent.com/nytimes/covid-19-data/master/us/counties.csv",
                parser="csv",
            ),
            OpenSource(
                name="Public-Demo-JSON",
                url="https://httpbin.org/json",
                parser="json",
            ),
            OpenSource(
                name="Public-RSS-Demo",
                url="https://hnrss.org/newest",
                parser="rss",
            ),
        ]
        self.sources = sources
        super().__init__(ParserConfig(
            name="OpenDataParser",
            base_url="",
            timeout=30,
            max_retries=2,
            rate_limit=2,
            max_concurrent=3,
            cache_ttl=300,
        ))

    async def _parse_impl(self, location: str, params: Dict[str, Any]) -> List[PropertyCreate]:
        results: List[PropertyCreate] = []

        async with EnhancedHTTPClient() as client:
            tasks = [self._fetch_and_transform(client, src, location) for src in self.sources]
            fetched = await asyncio.gather(*tasks, return_exceptions=True)

        for item in fetched:
            if isinstance(item, list):
                results.extend(item)
            elif isinstance(item, Exception):
                logger.warning(f"Open source fetch error: {item}")

        return results

    async def _fetch_and_transform(self, client: EnhancedHTTPClient, src: OpenSource, location: str) -> List[PropertyCreate]:
        try:
            if src.parser == "json":
                resp = await client.get(src.url)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                return self._map_json_to_properties(data, src, location)
            elif src.parser == "rss":
                resp = await client.get(src.url)
                if resp.status_code != 200:
                    return []
                text = resp.text
                return self._map_rss_to_properties(text, src, location)
            elif src.parser == "csv":
                resp = await client.get(src.url)
                if resp.status_code != 200:
                    return []
                text = resp.text
                return self._map_csv_to_properties(text, src, location)
        except Exception as e:
            logger.error(f"Failed to fetch {src.name}: {e}")
        return []

    def _map_json_to_properties(self, data: Any, src: OpenSource, location: str) -> List[PropertyCreate]:
        # Демонстрационное преобразование JSON в PropertyCreate
        results: List[PropertyCreate] = []
        try:
            slideshow = data.get("slideshow", {})
            slides = slideshow.get("slides", [])
            for slide in slides:
                title = slide.get("title", "")
                results.append(PropertyCreate(
                    title=title or "Open JSON Listing",
                    description=f"Source: {src.name}",
                    price=0,
                    currency="RUB",
                    address=location,
                    rooms=0,
                    source=src.name,
                    url=src.url,
                ))
        except Exception as e:
            logger.debug(f"Failed to parse JSON source: {e}")
        return results

    def _map_rss_to_properties(self, xml_text: str, src: OpenSource, location: str) -> List[PropertyCreate]:
        # Простейший парсинг RSS без зависимостей
        results: List[PropertyCreate] = []
        try:
            import re
            items = re.findall(r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?</item>", xml_text, re.S)
            for title, link in items[:10]:
                results.append(PropertyCreate(
                    title=title,
                    description=f"RSS item from {src.name}",
                    price=0,
                    currency="RUB",
                    address=location,
                    rooms=0,
                    source=src.name,
                    url=link,
                ))
        except Exception as e:
            logger.debug(f"Failed to parse RSS feed: {e}")
        return results

    def _map_csv_to_properties(self, csv_text: str, src: OpenSource, location: str) -> List[PropertyCreate]:
        results: List[PropertyCreate] = []
        try:
            import csv
            from io import StringIO
            reader = csv.DictReader(StringIO(csv_text))
            for i, row in enumerate(reader):
                if i >= 10:
                    break
                results.append(PropertyCreate(
                    title=row.get("county", "Open CSV Listing"),
                    description=f"CSV row from {src.name}",
                    price=0,
                    currency="RUB",
                    address=location,
                    rooms=0,
                    source=src.name,
                    url=src.url,
                ))
        except Exception:
            pass
        return results
