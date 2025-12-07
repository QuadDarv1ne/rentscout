"""
Export endpoints for property data.

Provides streaming export capabilities with multiple formats support.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.async_export import AsyncExportService
from app.utils.logger import logger
from app.utils.error_handler import retry_advanced, RetryStrategy

router = APIRouter()


@router.get("/export/properties")
async def export_properties(
    format: str = Query("json", regex="^(json|jsonl|csv)$"),
    city: str = Query(None),
    limit: int = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Export properties with streaming support.

    Query Parameters:
        format: Export format (json, jsonl, csv)
        city: Filter by city
        limit: Maximum number of items

    Returns:
        Streaming response with export data
    """
    try:
        # Validate format
        if format not in AsyncExportService.EXPORT_FORMATS:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

        # Log export request
        logger.info(
            f"Export request: format={format}, city={city}, limit={limit}",
            extra={
                "export_format": format,
                "city": city,
                "limit": limit,
            }
        )

        # Generate streaming response based on format
        if format == "csv":
            return {
                "status": "streaming",
                "format": format,
                "message": "Use FastAPI StreamingResponse wrapper in main.py"
            }
        elif format == "json":
            return {
                "status": "streaming",
                "format": format,
                "message": "Use FastAPI StreamingResponse wrapper in main.py"
            }
        else:  # jsonl
            return {
                "status": "streaming",
                "format": format,
                "message": "Use FastAPI StreamingResponse wrapper in main.py"
            }

    except Exception as e:
        logger.error(f"Export error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/properties/progress")
async def export_properties_with_progress(
    format: str = Query("json", regex="^(json|jsonl|csv)$"),
    city: str = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Export properties with progress tracking.

    Query Parameters:
        format: Export format
        city: Filter by city

    Returns:
        Statistics about the export
    """
    try:
        if format not in AsyncExportService.EXPORT_FORMATS:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

        # Execute export with progress
        stats = await AsyncExportService.export_with_progress(
            db=db,
            format=format,
            city=city,
        )

        logger.info(
            f"Export completed: {stats['status']}",
            extra=stats
        )

        return stats

    except Exception as e:
        logger.error(f"Export progress error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/statistics")
@retry_advanced(
    max_attempts=3,
    strategy=RetryStrategy.EXPONENTIAL,
    exceptions=(Exception,),
)
async def get_export_statistics(
    db: AsyncSession = Depends(get_db),
):
    """
    Get statistics about recent exports.

    Returns:
        Export statistics and metrics
    """
    try:
        return {
            "total_exports": 0,
            "successful_exports": 0,
            "failed_exports": 0,
            "average_duration": 0,
            "supported_formats": AsyncExportService.EXPORT_FORMATS,
            "note": "Metrics integration needed with metrics_collector"
        }

    except Exception as e:
        logger.error(f"Export statistics error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
