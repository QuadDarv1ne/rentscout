"""
Database session configuration and management.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool, PoolProxiedConnection

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create async engine with optimized connection pooling
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,  # Verify connection health before using
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=3600,  # Recycle connections after 1 hour
    poolclass=AsyncAdaptedQueuePool,
    pool_reset_on_return="rollback",
)

# Create session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session with performance monitoring.
    
    Usage:
        @app.get("/items")
        async def read_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    import time
    start_time = time.perf_counter()
    
    async with AsyncSessionLocal() as session:
        try:
            acquire_time = time.perf_counter() - start_time
            if acquire_time > 1.0:
                logger.warning(f"Slow DB session acquisition: {acquire_time:.2f}s")
            
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            total_time = time.perf_counter() - start_time
            if total_time > 5.0:
                logger.warning(f"Long DB session duration: {total_time:.2f}s")

async def init_db():
    """Initialize database connection with pool statistics."""
    try:
        # Test connection
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        logger.info("Database connection established")
        
        # Log pool configuration
        pool = engine.pool
        logger.info(f"Database pool configured: size={pool.size()}, max_overflow={pool.overflow()}")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

async def close_db():
    """Close database connection and log pool statistics."""
    # Log pool statistics before closing
    pool = engine.pool
    if hasattr(pool, 'checkedin') and hasattr(pool, 'checkedout'):
        logger.info(f"Database pool stats before closing: checkedin={pool.checkedin()}, checkedout={pool.checkedout()}")
    
    await engine.dispose()
    logger.info("Database connection closed")