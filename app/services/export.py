"""Сервис для экспорта результатов поиска в различные форматы."""

import csv
import json
from io import StringIO, BytesIO
from typing import List

from app.models.schemas import Property


class ExportService:
    """Сервис для экспорта свойств в различные форматы."""

    @staticmethod
    def to_csv(properties: List[Property]) -> str:
        """
        Экспортирует свойства в CSV формат.
        
        Args:
            properties: Список свойств для экспорта
            
        Returns:
            CSV строка
        """
        if not properties:
            return ""
        
        output = StringIO()
        
        # Определяем поля для экспорта
        fieldnames = [
            "id",
            "source",
            "external_id",
            "title",
            "price",
            "rooms",
            "area",
            "floor",
            "total_floors",
            "district",
            "city",
            "address",
            "contact_name",
            "contact_phone",
            "has_photos",
            "is_active",
            "description_preview",
            "link",
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for prop in properties:
            row = {
                "id": prop.id,
                "source": prop.source,
                "external_id": prop.external_id,
                "title": prop.title,
                "price": prop.price,
                "rooms": prop.rooms,
                "area": prop.area,
                "floor": prop.floor,
                "total_floors": prop.total_floors,
                "district": prop.location.get("district", "") if prop.location else "",
                "city": prop.location.get("city", "") if prop.location else "",
                "address": prop.address or (prop.location.get("address", "") if prop.location else ""),
                "contact_name": prop.contact_name,
                "contact_phone": prop.contact_phone,
                "has_photos": len(prop.photos) > 0 if prop.photos else False,
                "is_active": prop.is_active,
                "description_preview": (prop.description[:100] + "...") if prop.description else "",
                "link": prop.link,
            }
            writer.writerow(row)
        
        return output.getvalue()

    @staticmethod
    def to_json(properties: List[Property], pretty: bool = True) -> str:
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
                "id": prop.id,
                "source": prop.source,
                "external_id": prop.external_id,
                "title": prop.title,
                "price": prop.price,
                "currency": prop.currency,
                "rooms": prop.rooms,
                "area": prop.area,
                "floor": prop.floor,
                "total_floors": prop.total_floors,
                "contact_name": prop.contact_name,
                "contact_phone": prop.contact_phone,
                "location": prop.location,
                "photos": prop.photos,
                "is_active": prop.is_active,
                "is_verified": prop.is_verified,
                "description": prop.description,
                "link": prop.link,
                "created_at": prop.created_at.isoformat() if prop.created_at else None,
                "last_updated": prop.last_updated.isoformat() if prop.last_updated else None,
            }
            data.append(item)
        
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        else:
            return json.dumps(data, ensure_ascii=False)

    @staticmethod
    def to_jsonl(properties: List[Property]) -> str:
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
                "id": prop.id,
                "source": prop.source,
                "external_id": prop.external_id,
                "title": prop.title,
                "price": prop.price,
                "rooms": prop.rooms,
                "area": prop.area,
                "location": prop.location,
                "link": prop.link,
            }
            lines.append(json.dumps(item, ensure_ascii=False))
        
        return "\n".join(lines)
