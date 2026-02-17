
import os
import sys
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Добавить корень проекта в PYTHONPATH для корректного импорта app.*
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

def pytest_configure():
    pytest.test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')


# Database fixtures for PostgreSQL tests
@pytest_asyncio.fixture
async def db_engine():
    """Create test database engine."""
    from app.db.models.property import Base
    
    # Use single test database file
    import os
    db_path = os.path.join(os.path.dirname(__file__), "test_database.db")
    
    try:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            echo=False,
            future=True,
        )
        
        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        yield engine
        
        # Drop tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        await engine.dispose()
    finally:
        # Clean up database file
        if os.path.exists(db_path):
            os.unlink(db_path)


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Create test database session."""
    async_session = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="session", autouse=True)
def disable_rate_limiting():
    """Отключить rate limiting для всех тестов."""
    from unittest.mock import patch
    
    # Патчим RateLimitMiddleware чтобы не применять ограничения
    async def passthrough_dispatch(self, request, call_next):
        return await call_next(request)
    
    with patch('app.utils.ip_ratelimiter.RateLimitMiddleware.dispatch', new=passthrough_dispatch):
        yield

