"""
Cache management endpoints.

Provides cache control operations:
- Clear cache
- Get cache statistics
- Invalidate specific keys
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

from app.utils.logger import logger
from app.services.advanced_cache import advanced_cache_manager
from app.utils.query_cache import get_query_cache

router = APIRouter(prefix="/cache", tags=["Cache", "Management"])


class CacheStatsResponse(BaseModel):
    """Cache statistics response."""
    redis_connected: bool = Field(..., description="Redis connection status")
    total_keys: int = Field(..., description="Total keys in cache")
    memory_used: str = Field(..., description="Memory used by cache")
    hit_rate: float = Field(..., description="Cache hit rate percentage")
    query_cache_stats: Dict[str, Any] = Field(default_factory=dict, description="Query cache statistics")


class CacheClearRequest(BaseModel):
    """Request to clear cache."""
    pattern: Optional[str] = Field(None, description="Pattern to match keys (e.g., 'search*')")
    prefix: Optional[str] = Field(None, description="Key prefix to clear")


class CacheClearResponse(BaseModel):
    """Response from cache clear operation."""
    cleared: bool = Field(..., description="Whether cache was cleared")
    keys_deleted: int = Field(..., description="Number of keys deleted")
    message: str = Field(..., description="Result message")


@router.get("/stats", response_model=CacheStatsResponse)
async def get_cache_stats():
    """
    Get cache statistics.

    Returns:
        Cache statistics including hit rate, memory usage, and key count
    """
    try:
        from app.utils.redis import get_redis_client
        redis_client = get_redis_client()

        if not redis_client:
            return CacheStatsResponse(
                redis_connected=False,
                total_keys=0,
                memory_used="0B",
                hit_rate=0.0,
                query_cache_stats={},
            )

        # Get Redis info
        info = await redis_client.info("memory")
        keyspace = await redis_client.info("keyspace")
        
        # Count keys
        cursor = 0
        total_keys = 0
        async for _ in redis_client.scan_iter(match="*"):
            total_keys += 1
            if total_keys >= 10000:  # Limit for performance
                break

        # Get query cache stats
        query_cache = get_query_cache()
        query_stats = query_cache.get_stats()

        memory_used = info.get("used_memory_human", "0B")

        return CacheStatsResponse(
            redis_connected=True,
            total_keys=total_keys,
            memory_used=memory_used,
            hit_rate=0.0,  # Would need to track globally
            query_cache_stats=query_stats,
        )

    except Exception as e:
        logger.error(f"Cache stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear", response_model=CacheClearResponse)
async def clear_cache(request: CacheClearRequest = None):
    """
    Clear cache entries.

    Args:
        request: Clear request with optional pattern/prefix

    Returns:
        Number of keys cleared
    """
    try:
        from app.utils.redis import get_redis_client
        redis_client = get_redis_client()

        if not redis_client:
            return CacheClearResponse(
                cleared=False,
                keys_deleted=0,
                message="Redis not available",
            )

        keys_deleted = 0

        if request and request.pattern:
            # Clear by pattern
            async for key in redis_client.scan_iter(match=request.pattern):
                await redis_client.delete(key)
                keys_deleted += 1
            message = f"Cleared {keys_deleted} keys matching pattern '{request.pattern}'"

        elif request and request.prefix:
            # Clear by prefix
            pattern = f"{request.prefix}*"
            async for key in redis_client.scan_iter(match=pattern):
                await redis_client.delete(key)
                keys_deleted += 1
            message = f"Cleared {keys_deleted} keys with prefix '{request.prefix}'"

        else:
            # Clear all cache keys (common prefixes)
            cache_prefixes = [
                "cache:*",
                "query_cache:*",
                "parser_cache:*",
                "search_cache:*",
            ]
            
            for prefix in cache_prefixes:
                async for key in redis_client.scan_iter(match=prefix):
                    await redis_client.delete(key)
                    keys_deleted += 1
            
            message = f"Cleared {keys_deleted} cache keys"

        logger.info(f"Cache cleared: {keys_deleted} keys")

        return CacheClearResponse(
            cleared=True,
            keys_deleted=keys_deleted,
            message=message,
        )

    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invalidate")
async def invalidate_cache(
    query_type: str = Query(..., description="Query type to invalidate"),
    params: Optional[str] = Query(None, description="JSON-encoded params (optional)"),
):
    """
    Invalidate specific cached queries.

    Args:
        query_type: Type of query (e.g., "search_properties")
        params: Optional JSON-encoded params for specific invalidation

    Returns:
        Invalidation result
    """
    try:
        import json
        query_cache = get_query_cache()

        params_dict = {}
        if params:
            try:
                params_dict = json.loads(params)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON params")

        count = await query_cache.invalidate(query_type, params_dict if params_dict else None)

        return {
            "invalidated": True,
            "keys_deleted": count,
            "query_type": query_type,
        }

    except Exception as e:
        logger.error(f"Cache invalidate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/keys")
async def list_cache_keys(
    pattern: str = Query("cache:*", description="Pattern to match"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum keys to return"),
):
    """
    List cache keys matching pattern.

    Args:
        pattern: Redis pattern to match
        limit: Maximum number of keys to return

    Returns:
        List of matching keys
    """
    try:
        from app.utils.redis import get_redis_client
        redis_client = get_redis_client()

        if not redis_client:
            return {"keys": [], "total": 0}

        keys = []
        async for key in redis_client.scan_iter(match=pattern):
            keys.append(key)
            if len(keys) >= limit:
                break

        return {
            "keys": keys,
            "total": len(keys),
            "pattern": pattern,
        }

    except Exception as e:
        logger.error(f"Cache list keys error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/warm")
async def warm_cache(
    queries: List[Dict[str, Any]],
):
    """
    Warm cache with specific queries.

    Args:
        queries: List of queries to execute and cache

    Returns:
        Warming result
    """
    try:
        from app.services.optimized_search import OptimizedSearchService
        
        search_service = OptimizedSearchService()
        warmed = 0
        errors = 0

        for query in queries:
            try:
                city = query.get("city", "Москва")
                property_type = query.get("property_type", "Квартира")
                
                await search_service.search_cached(
                    query="",
                    city=city,
                    filters={"property_type": property_type}
                )
                warmed += 1
            except Exception as e:
                logger.error(f"Cache warm error for {query}: {e}")
                errors += 1

        return {
            "warmed": warmed,
            "errors": errors,
            "total": len(queries),
        }

    except Exception as e:
        logger.error(f"Cache warm error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
