"""
Smart caching layer for popular queries with automatic invalidation.
"""
import json
import hashlib
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar
from datetime import datetime, timedelta
from functools import wraps

from app.services.cache import cache_manager
from app.utils.logger import logger

T = TypeVar('T')


class QueryCache:
    """Smart caching for database queries with automatic invalidation."""

    # Cache configuration
    DEFAULT_TTL = 300  # 5 minutes
    POPULAR_QUERIES_TTL = 3600  # 1 hour
    FREQUENTLY_ACCESSED_TTL = 1800  # 30 minutes

    # Popular query patterns
    POPULAR_QUERIES = {
        'cities': 'SELECT DISTINCT city FROM properties',
        'property_types': 'SELECT DISTINCT property_type FROM properties',
        'sources': 'SELECT DISTINCT source FROM properties',
        'price_ranges': 'SELECT min(price), max(price) FROM properties WHERE is_active=true',
    }

    @staticmethod
    def _generate_cache_key(namespace: str, **kwargs) -> str:
        """
        Generate cache key from namespace and parameters.

        Args:
            namespace: Cache namespace
            **kwargs: Query parameters

        Returns:
            Cache key
        """
        # Sort kwargs for consistent hashing
        params = json.dumps(kwargs, sort_keys=True, default=str)
        param_hash = hashlib.md5(params.encode()).hexdigest()
        return f"query:{namespace}:{param_hash}"

    @staticmethod
    def _determine_ttl(query_type: str, access_count: int = 0) -> int:
        """
        Determine TTL based on query type and access patterns.

        Args:
            query_type: Type of query
            access_count: Number of times query was accessed

        Returns:
            TTL in seconds
        """
        # Popular queries get longer cache
        if query_type in QueryCache.POPULAR_QUERIES:
            return QueryCache.POPULAR_QUERIES_TTL

        # Frequently accessed queries get medium cache
        if access_count > 10:
            return QueryCache.FREQUENTLY_ACCESSED_TTL

        # Others get standard cache
        return QueryCache.DEFAULT_TTL

    @staticmethod
    async def get_or_fetch(
        cache_key: str,
        fetch_func: Callable,
        ttl: Optional[int] = None,
        **fetch_kwargs
    ) -> Any:
        """
        Get from cache or fetch and cache result.

        Args:
            cache_key: Cache key
            fetch_func: Function to fetch data if not cached
            ttl: Time to live in seconds
            **fetch_kwargs: Arguments to pass to fetch_func

        Returns:
            Cached or fetched data
        """
        ttl = ttl or QueryCache.DEFAULT_TTL

        # Try to get from cache
        try:
            cached_data = await cache_manager.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_data
        except Exception as e:
            logger.warning(f"Cache get error: {str(e)}")

        # Fetch data
        try:
            data = await fetch_func(**fetch_kwargs)
        except Exception as e:
            logger.error(f"Fetch error: {str(e)}")
            raise

        # Cache result
        try:
            await cache_manager.set(cache_key, data, ttl=ttl)
        except Exception as e:
            logger.warning(f"Cache set error: {str(e)}")

        return data

    @staticmethod
    async def invalidate_pattern(pattern: str) -> int:
        """
        Invalidate cache keys matching a pattern.

        Args:
            pattern: Pattern to match (e.g., "query:properties:*")

        Returns:
            Number of keys deleted
        """
        try:
            count = await cache_manager.delete_pattern(pattern)
            logger.info(f"Invalidated {count} cache keys matching {pattern}")
            return count
        except Exception as e:
            logger.error(f"Cache invalidation error: {str(e)}")
            return 0

    @staticmethod
    async def invalidate_related(
        entity_type: str,
        entity_id: Optional[int] = None
    ) -> int:
        """
        Invalidate related cache entries when entity changes.

        Args:
            entity_type: Type of entity (e.g., 'property', 'city')
            entity_id: ID of entity (None for global invalidation)

        Returns:
            Number of keys deleted
        """
        patterns = []

        if entity_type == 'property':
            patterns = [
                f"query:properties:*",
                f"query:price_range:*",
                f"query:top_properties:*",
            ]
        elif entity_type == 'city':
            patterns = [
                f"query:*:{entity_id}:*" if entity_id else "query:cities:*",
                f"query:properties:*",
            ]

        total_deleted = 0
        for pattern in patterns:
            deleted = await QueryCache.invalidate_pattern(pattern)
            total_deleted += deleted

        return total_deleted


def cached_query(namespace: str, ttl: Optional[int] = None):
    """
    Decorator for caching query results.

    Args:
        namespace: Cache namespace
        ttl: Time to live in seconds

    Example:
        @cached_query('popular_properties', ttl=3600)
        async def get_popular_properties(db):
            # query logic
            return properties
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            cache_key = QueryCache._generate_cache_key(namespace, **kwargs)
            cache_ttl = ttl or QueryCache._determine_ttl(namespace)

            return await QueryCache.get_or_fetch(
                cache_key,
                func,
                cache_ttl,
                *args,
                **kwargs
            )

        return wrapper

    return decorator


class PopularQueriesCache:
    """Cache for commonly accessed query results."""

    @staticmethod
    async def get_popular_properties(
        db,
        city: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get popular properties with caching."""
        cache_key = QueryCache._generate_cache_key(
            'popular_properties',
            city=city,
            limit=limit
        )

        async def fetch():
            # This would be actual DB query
            return []

        return await QueryCache.get_or_fetch(
            cache_key,
            fetch,
            QueryCache.POPULAR_QUERIES_TTL
        )

    @staticmethod
    async def get_price_stats(
        db,
        city: Optional[str] = None
    ) -> Dict[str, float]:
        """Get price statistics with caching."""
        cache_key = QueryCache._generate_cache_key(
            'price_stats',
            city=city
        )

        async def fetch():
            # This would be actual DB query
            return {}

        return await QueryCache.get_or_fetch(
            cache_key,
            fetch,
            QueryCache.POPULAR_QUERIES_TTL
        )

    @staticmethod
    async def get_cities(db) -> List[str]:
        """Get list of cities with caching."""
        cache_key = QueryCache._generate_cache_key('cities')

        async def fetch():
            # This would be actual DB query
            return []

        return await QueryCache.get_or_fetch(
            cache_key,
            fetch,
            QueryCache.POPULAR_QUERIES_TTL
        )

    @staticmethod
    async def get_property_types(db) -> List[str]:
        """Get list of property types with caching."""
        cache_key = QueryCache._generate_cache_key('property_types')

        async def fetch():
            # This would be actual DB query
            return []

        return await QueryCache.get_or_fetch(
            cache_key,
            fetch,
            QueryCache.POPULAR_QUERIES_TTL
        )
