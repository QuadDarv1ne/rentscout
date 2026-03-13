"""
Batch operations for efficient bulk processing.

Provides endpoints for:
- Bulk property operations
- Batch updates
- Mass delete
- Bulk upsert
"""
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.db.models.session import get_db
from app.db.models.property import Property
from app.utils.logger import logger

router = APIRouter(prefix="/batch", tags=["Batch Operations"])


class BulkPropertyUpdate(BaseModel):
    """Bulk update request."""
    ids: List[int] = Field(..., description="Property IDs to update")
    updates: Dict[str, Any] = Field(..., description="Fields to update")


class BulkDeleteRequest(BaseModel):
    """Bulk delete request."""
    ids: List[int] = Field(..., description="Property IDs to delete")
    soft_delete: bool = Field(default=True, description="If True, set is_active=False instead of deleting")


class BulkUpsertRequest(BaseModel):
    """Bulk upsert request."""
    properties: List[Dict[str, Any]] = Field(..., description="Properties to upsert")


class BatchOperationResponse(BaseModel):
    """Response for batch operations."""
    success: bool = Field(..., description="Operation success status")
    processed: int = Field(..., description="Number of items processed")
    failed: int = Field(..., description="Number of items failed")
    errors: List[str] = Field(default_factory=list, description="Error messages")


@router.post("/update", response_model=BatchOperationResponse)
async def bulk_update_properties(
    request: BulkPropertyUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update multiple properties in a single operation.

    Args:
        request: Bulk update request with IDs and fields to update
        db: Database session

    Returns:
        Operation result with counts
    """
    try:
        if not request.ids:
            return BatchOperationResponse(success=True, processed=0, failed=0)

        # Build update query
        stmt = (
            update(Property)
            .where(Property.id.in_(request.ids))
            .values(**request.updates)
        )

        result = await db.execute(stmt)
        await db.commit()

        processed = result.rowcount

        logger.info(f"Bulk updated {processed} properties")

        return BatchOperationResponse(
            success=True,
            processed=processed,
            failed=len(request.ids) - processed,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Bulk update error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete", response_model=BatchOperationResponse)
async def bulk_delete_properties(
    request: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete multiple properties in a single operation.

    Args:
        request: Bulk delete request
        db: Database session

    Returns:
        Operation result with counts
    """
    try:
        if not request.ids:
            return BatchOperationResponse(success=True, processed=0, failed=0)

        if request.soft_delete:
            # Soft delete: set is_active=False
            stmt = (
                update(Property)
                .where(Property.id.in_(request.ids))
                .values(is_active=False)
            )
        else:
            # Hard delete
            stmt = delete(Property).where(Property.id.in_(request.ids))

        result = await db.execute(stmt)
        await db.commit()

        processed = result.rowcount

        logger.info(f"Bulk {'soft deleted' if request.soft_delete else 'deleted'} {processed} properties")

        return BatchOperationResponse(
            success=True,
            processed=processed,
            failed=len(request.ids) - processed,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Bulk delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upsert", response_model=BatchOperationResponse)
async def bulk_upsert_properties(
    request: BulkUpsertRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk insert or update properties.

    Uses PostgreSQL's ON CONFLICT clause for efficient upsert.

    Args:
        request: Bulk upsert request
        db: Database session

    Returns:
        Operation result with counts
    """
    try:
        if not request.properties:
            return BatchOperationResponse(success=True, processed=0, failed=0)

        from sqlalchemy.dialects.postgresql import insert

        # Prepare data for bulk insert
        properties_data = []
        for prop in request.properties:
            # Extract location fields
            location = prop.get("location", {})
            
            properties_data.append({
                "source": prop.get("source"),
                "external_id": prop.get("external_id"),
                "title": prop.get("title"),
                "description": prop.get("description"),
                "link": prop.get("link"),
                "price": prop.get("price"),
                "rooms": prop.get("rooms"),
                "area": prop.get("area"),
                "city": location.get("city"),
                "district": location.get("district"),
                "address": location.get("address"),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "location": location,
                "photos": prop.get("photos", []),
            })

        # Build upsert statement
        stmt = insert(Property).values(properties_data)
        stmt = stmt.on_conflict_do_update(
            index_elements=['source', 'external_id'],
            set_={
                "title": stmt.excluded.title,
                "price": stmt.excluded.price,
                "rooms": stmt.excluded.rooms,
                "area": stmt.excluded.area,
                "last_seen": stmt.excluded.last_seen,
            }
        )

        result = await db.execute(stmt)
        await db.commit()

        processed = result.rowcount if result.rowcount else len(properties_data)

        logger.info(f"Bulk upserted {processed} properties")

        return BatchOperationResponse(
            success=True,
            processed=processed,
            failed=0,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Bulk upsert error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/activate", response_model=BatchOperationResponse)
async def bulk_activate_properties(
    ids: List[int] = Body(..., embed=True, description="Property IDs to activate"),
    db: AsyncSession = Depends(get_db)
):
    """
    Activate multiple properties.

    Args:
        ids: List of property IDs
        db: Database session

    Returns:
        Operation result
    """
    try:
        if not ids:
            return BatchOperationResponse(success=True, processed=0, failed=0)

        stmt = (
            update(Property)
            .where(Property.id.in_(ids))
            .values(is_active=True)
        )

        result = await db.execute(stmt)
        await db.commit()

        processed = result.rowcount

        logger.info(f"Bulk activated {processed} properties")

        return BatchOperationResponse(
            success=True,
            processed=processed,
            failed=len(ids) - processed,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Bulk activate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deactivate", response_model=BatchOperationResponse)
async def bulk_deactivate_properties(
    ids: List[int] = Body(..., embed=True, description="Property IDs to deactivate"),
    db: AsyncSession = Depends(get_db)
):
    """
    Deactivate multiple properties.

    Args:
        ids: List of property IDs
        db: Database session

    Returns:
        Operation result
    """
    try:
        if not ids:
            return BatchOperationResponse(success=True, processed=0, failed=0)

        stmt = (
            update(Property)
            .where(Property.id.in_(ids))
            .values(is_active=False)
        )

        result = await db.execute(stmt)
        await db.commit()

        processed = result.rowcount

        logger.info(f"Bulk deactivated {processed} properties")

        return BatchOperationResponse(
            success=True,
            processed=processed,
            failed=len(ids) - processed,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Bulk deactivate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_batch_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Get statistics for batch operations.

    Returns counts of properties by status.
    """
    try:
        from sqlalchemy import func

        result = await db.execute(
            select(
                func.count(Property.id).label("total"),
                func.sum(func.case((Property.is_active == True, 1), else_=0)).label("active"),
                func.sum(func.case((Property.is_active == False, 1), else_=0)).label("inactive"),
                func.sum(func.case((Property.is_verified == True, 1), else_=0)).label("verified"),
            )
        )

        row = result.one()

        return {
            "total": row.total or 0,
            "active": row.active or 0,
            "inactive": row.inactive or 0,
            "verified": row.verified or 0,
        }

    except Exception as e:
        logger.error(f"Batch stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify", response_model=BatchOperationResponse)
async def bulk_verify_properties(
    ids: List[int] = Body(..., embed=True, description="Property IDs to verify"),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify multiple properties.

    Args:
        ids: List of property IDs
        db: Database session

    Returns:
        Operation result
    """
    try:
        if not ids:
            return BatchOperationResponse(success=True, processed=0, failed=0)

        stmt = (
            update(Property)
            .where(Property.id.in_(ids))
            .values(is_verified=True)
        )

        result = await db.execute(stmt)
        await db.commit()

        processed = result.rowcount

        logger.info(f"Bulk verified {processed} properties")

        return BatchOperationResponse(
            success=True,
            processed=processed,
            failed=len(ids) - processed,
        )

    except Exception as e:
        await db.rollback()
        logger.error(f"Bulk verify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
