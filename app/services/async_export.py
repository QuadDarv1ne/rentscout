"""
Asynchronous export service for large datasets.

Provides streaming export capabilities with progress tracking for large property datasets.
"""
import asyncio
from typing import AsyncGenerator, Dict, List, Optional, Any
from datetime import datetime
import csv
import json
import io

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.property import Property
from app.utils.logger import logger
from app.utils.metrics import metrics_collector


class AsyncExportService:
    """Service for asynchronous export of large datasets."""

    BATCH_SIZE = 1000  # Process in batches to avoid memory issues
    EXPORT_FORMATS = ['csv', 'json', 'jsonl', 'parquet']

    @staticmethod
    async def export_properties_streaming(
        db: AsyncSession,
        format: str = 'json',
        city: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> AsyncGenerator[str, None]:
        """
        Export properties with streaming to handle large datasets.

        Args:
            db: Database session
            format: Export format (csv, json, jsonl)
            city: Filter by city
            limit: Maximum number of items
            offset: Number of items to skip

        Yields:
            Chunks of exported data
        """
        if format not in AsyncExportService.EXPORT_FORMATS:
            raise ValueError(f"Unsupported format: {format}")

        start_time = datetime.utcnow()
        total_items = 0

        try:
            if format == 'csv':
                async for chunk in AsyncExportService._export_csv(
                    db, city, limit, offset
                ):
                    total_items += len(chunk.split('\n')) - 1
                    yield chunk

            elif format == 'json':
                async for chunk in AsyncExportService._export_json(
                    db, city, limit, offset
                ):
                    total_items += 1
                    yield chunk

            elif format == 'jsonl':
                async for chunk in AsyncExportService._export_jsonl(
                    db, city, limit, offset
                ):
                    total_items += 1
                    yield chunk

            # Record export metrics
            duration = (datetime.utcnow() - start_time).total_seconds()
            metrics_collector.record_export(
                format=format,
                status='success',
                duration=duration,
                items_count=total_items
            )

        except Exception as e:
            logger.error(
                f"Export error: {str(e)}",
                extra={"format": format, "error": str(e)}
            )
            metrics_collector.record_export(
                format=format,
                status='error',
                duration=(datetime.utcnow() - start_time).total_seconds(),
                items_count=0
            )
            raise

    @staticmethod
    async def _export_csv(
        db: AsyncSession,
        city: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> AsyncGenerator[str, None]:
        """Export as CSV with streaming."""
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                'id', 'source', 'external_id', 'title', 'price', 'area',
                'rooms', 'city', 'district', 'url', 'property_type', 'created_at'
            ]
        )

        # Write header
        writer.writeheader()
        yield output.getvalue()
        output.truncate(0)
        output.seek(0)

        # Fetch and write data in batches
        batch_offset = offset
        while True:
            # Fetch batch
            properties = await AsyncExportService._fetch_batch(
                db, city, AsyncExportService.BATCH_SIZE, batch_offset
            )

            if not properties:
                break

            # Write batch
            for prop in properties:
                writer.writerow({
                    'id': prop.id,
                    'source': prop.source,
                    'external_id': prop.external_id,
                    'title': prop.title,
                    'price': prop.price,
                    'area': prop.area,
                    'rooms': prop.rooms,
                    'city': prop.city,
                    'district': prop.district,
                    'url': prop.url,
                    'property_type': prop.property_type,
                    'created_at': prop.created_at,
                })

            yield output.getvalue()
            output.truncate(0)
            output.seek(0)

            batch_offset += AsyncExportService.BATCH_SIZE

            # Check limit
            if limit and batch_offset - offset >= limit:
                break

    @staticmethod
    async def _export_json(
        db: AsyncSession,
        city: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> AsyncGenerator[str, None]:
        """Export as JSON array with streaming."""
        items = []
        batch_offset = offset

        # Start array
        yield '[\n'

        first_item = True
        while True:
            # Fetch batch
            properties = await AsyncExportService._fetch_batch(
                db, city, AsyncExportService.BATCH_SIZE, batch_offset
            )

            if not properties:
                break

            # Convert to dicts
            for prop in properties:
                if not first_item:
                    yield ',\n'
                else:
                    first_item = False

                prop_dict = {
                    'id': prop.id,
                    'source': prop.source,
                    'external_id': prop.external_id,
                    'title': prop.title,
                    'price': prop.price,
                    'area': prop.area,
                    'rooms': prop.rooms,
                    'city': prop.city,
                    'district': prop.district,
                    'url': prop.url,
                    'property_type': prop.property_type,
                    'created_at': prop.created_at.isoformat() if prop.created_at else None,
                }
                yield json.dumps(prop_dict, ensure_ascii=False)

            batch_offset += AsyncExportService.BATCH_SIZE

            # Check limit
            if limit and batch_offset - offset >= limit:
                break

        # End array
        yield '\n]'

    @staticmethod
    async def _export_jsonl(
        db: AsyncSession,
        city: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> AsyncGenerator[str, None]:
        """Export as JSONL (newline-delimited JSON)."""
        batch_offset = offset

        while True:
            # Fetch batch
            properties = await AsyncExportService._fetch_batch(
                db, city, AsyncExportService.BATCH_SIZE, batch_offset
            )

            if not properties:
                break

            # Write batch
            output = io.StringIO()
            for prop in properties:
                prop_dict = {
                    'id': prop.id,
                    'source': prop.source,
                    'external_id': prop.external_id,
                    'title': prop.title,
                    'price': prop.price,
                    'area': prop.area,
                    'rooms': prop.rooms,
                    'city': prop.city,
                    'district': prop.district,
                    'url': prop.url,
                    'property_type': prop.property_type,
                    'created_at': prop.created_at.isoformat() if prop.created_at else None,
                }
                output.write(json.dumps(prop_dict, ensure_ascii=False) + '\n')

            yield output.getvalue()

            batch_offset += AsyncExportService.BATCH_SIZE

            # Check limit
            if limit and batch_offset - offset >= limit:
                break

    @staticmethod
    async def _fetch_batch(
        db: AsyncSession,
        city: Optional[str] = None,
        limit: int = BATCH_SIZE,
        offset: int = 0,
    ) -> List[Property]:
        """Fetch a batch of properties."""
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        query = select(Property)

        if city:
            query = query.where(Property.city == city)

        query = query.limit(limit).offset(offset)

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def export_with_progress(
        db: AsyncSession,
        format: str = 'json',
        city: Optional[str] = None,
        on_progress: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Export with progress tracking callback.

        Args:
            db: Database session
            format: Export format
            city: Filter by city
            on_progress: Callback function(current, total) for progress updates

        Returns:
            Export statistics
        """
        start_time = datetime.utcnow()
        total_items = 0
        chunks = []

        try:
            async for chunk in AsyncExportService.export_properties_streaming(
                db, format, city
            ):
                chunks.append(chunk)
                total_items += 1

                if on_progress:
                    await on_progress(total_items)

            duration = (datetime.utcnow() - start_time).total_seconds()

            return {
                'status': 'success',
                'format': format,
                'items': total_items,
                'duration_seconds': round(duration, 2),
                'chunks': len(chunks),
            }

        except Exception as e:
            logger.error(f"Export with progress error: {str(e)}")
            return {
                'status': 'error',
                'format': format,
                'error': str(e),
                'items': total_items,
                'duration_seconds': round(
                    (datetime.utcnow() - start_time).total_seconds(), 2
                ),
            }
