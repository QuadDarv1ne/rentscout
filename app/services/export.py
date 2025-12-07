"""Сервис для экспорта результатов поиска в различные форматы."""

import csv
import json
from io import StringIO
from typing import List

from app.models.schemas import PropertyCreate


class ExportService:
    """Сервис для экспорта свойств в различные форматы."""

    @staticmethod
    def to_csv(properties: List[PropertyCreate]) -> str:
        """
        Экспортирует свойства в CSV формат.
        
        Args:
            properties: Список свойств для экспорта
            
        Returns:
            CSV строка
        """
        output = StringIO()
        
        # Определяем поля для экспорта
        fieldnames = [
            "title",
            "price",
            "url",
            "source",
            "external_id",
            "city",
            "property_type",
            "rooms",
            "area",
            "floor",
            "total_floors",
            "address",
            "description",
            "photos",
            "location",
            "features",
            "contact_name",
            "contact_phone",
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for prop in properties:
            row = {
                "title": prop.title,
                "price": prop.price,
                "url": prop.link or "",
                "source": prop.source,
                "external_id": prop.external_id,
                "city": prop.city or "",
                "property_type": getattr(prop, "property_type", ""),
                "rooms": prop.rooms or "",
                "area": prop.area or "",
                "floor": prop.floor or "",
                "total_floors": prop.total_floors or "",
                "address": prop.address or "",
                "description": (prop.description[:200] + "...") if prop.description and len(prop.description) > 200 else (prop.description or ""),
                "photos": "; ".join(prop.photos) if prop.photos else "",
                "location": json.dumps(prop.location, ensure_ascii=False) if prop.location else "",
                "features": json.dumps(prop.features, ensure_ascii=False) if prop.features else "",
                "contact_name": prop.contact_name or "",
                "contact_phone": prop.contact_phone or "",
            }
            writer.writerow(row)
        
        return output.getvalue()

    @staticmethod
    def to_json(properties: List[PropertyCreate], pretty: bool = True) -> str:
        """
        Экспортирует свойства в JSON формат.
        
        Args:
            properties: Список свойств для экспорта
            pretty: Форматировать ли JSON с отступами
            
        Returns:
            JSON строка
        """
        data = []
        
        for prop in properties:
            item = {
                "title": prop.title,
                "price": prop.price,
                "currency": prop.currency or "RUB",
                "url": prop.link or "",
                "source": prop.source,
                "external_id": prop.external_id,
                "city": prop.city,
                "rooms": prop.rooms,
                "area": prop.area,
                "floor": prop.floor,
                "total_floors": prop.total_floors,
                "address": prop.address,
                "description": prop.description,
                "photos": prop.photos,
                "location": prop.location,
                "features": prop.features,
                "contact_name": prop.contact_name,
                "contact_phone": prop.contact_phone,
            }
            data.append(item)
        
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        else:
            return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def to_jsonl(properties: List[PropertyCreate]) -> str:
        """
        Экспортирует свойства в JSONL формат (JSON Lines).
        Каждая строка содержит один объект JSON.
        
        Args:
            properties: Список свойств для экспорта
            
        Returns:
            JSONL строка
        """
        lines = []
        
        for prop in properties:
            item = {
                "title": prop.title,
                "price": prop.price,
                "url": prop.link or "",
                "source": prop.source,
                "external_id": prop.external_id,
                "city": prop.city,
                "rooms": prop.rooms,
                "area": prop.area,
                "location": prop.location,
                "contact_phone": prop.contact_phone,
            }
            lines.append(json.dumps(item, ensure_ascii=False))
        
        return "\n".join(lines)
