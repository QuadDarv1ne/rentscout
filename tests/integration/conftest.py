"""
Конфигурация для интеграционных тестов.

Интеграционные тесты используют реальную базу данных и Redis.
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.config import settings
from app.db.models.session import get_db, init_db, close_db


# =============================================================================
# Test Database Configuration
# =============================================================================

TEST_DATABASE_URL = "postgresql+asyncpg://rentscout:test_password@localhost:5432/rentscout_integration_test"
TEST_REDIS_URL = "redis://localhost:6379/0"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Создание event loop для сессионных фикстур."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Создание тестового двигателя БД."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,  # Установите True для отладки SQL запросов
        poolclass=StaticPool,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def test_session_factory(test_engine):
    """Создание фабрики сессий для тестов."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return async_session


@pytest.fixture(scope="function")
async def db_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """
    Создание новой сессии БД для каждого теста.
    
    Каждый тест работает в изолированной транзакции,
    которая откатывается после завершения теста.
    """
    session = test_session_factory()
    
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture(scope="session")
async def app_with_test_db(test_engine):
    """
    Настройка приложения для использования тестовой БД.
    
    Переопределяет зависимость get_db для использования тестовой сессии.
    """
    from app.main import lifespan
    
    # Инициализация таблиц в тестовой БД
    async with test_engine.begin() as conn:
        from app.db.models.property import Property
        from app.db.models.bookmarks import Bookmark
        from app.db.models.ml_price_history import MLPriceHistory
        
        # Импорт всех моделей для создания таблиц
        from sqlalchemy import MetaData
        metadata = MetaData()
        
        # Создаём таблицы
        await conn.run_sync(metadata.create_all)
    
    yield app


@pytest.fixture
async def client(app_with_test_db) -> AsyncGenerator[AsyncClient, None]:
    """
    Создание тестового HTTP клиента.
    
    Клиент использует тестовую БД и не делает реальных HTTP запросов вовне.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app_with_test_db),
        base_url="http://test"
    ) as ac:
        yield ac


# =============================================================================
# Helper Fixtures
# =============================================================================

@pytest.fixture
def sample_property_data() -> dict:
    """Пример данных объявления для тестов."""
    return {
        "title": "2-к квартира, 54 м²",
        "price": 50000,
        "rooms": 2,
        "area": 54.0,
        "city": "Москва",
        "district": "ЦАО",
        "source": "avito",
        "url": "https://avito.ru/test123",
        "description": "Отличная квартира в центре",
    }


@pytest.fixture
def sample_user_data() -> dict:
    """Пример данных пользователя для тестов."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "StrongPass123!",
    }


@pytest.fixture
async def authenticated_client(client: AsyncClient, sample_user_data) -> AsyncGenerator[tuple, None]:
    """
    Клиент с аутентификацией.
    
    Автоматически регистрирует пользователя и добавляет токен в заголовки.
    """
    # Регистрация
    await client.post("/api/auth/register", json=sample_user_data)
    
    # Логин
    login_response = await client.post(
        "/api/auth/login",
        data={
            "username": sample_user_data["username"],
            "password": sample_user_data["password"],
        }
    )
    
    tokens = login_response.json()
    access_token = tokens["access_token"]
    
    # Клиент с токеном
    client.headers["Authorization"] = f"Bearer {access_token}"
    
    yield client, tokens


# =============================================================================
# Database Cleanup
# =============================================================================

@pytest.fixture(autouse=True)
async def cleanup_database(db_session: AsyncSession):
    """
    Автоматическая очистка БД после каждого теста.
    
    Использует транзакцию для отката всех изменений.
    """
    # До теста - чисто (предыдущий тест уже откатился)
    yield
    
    # После теста - откат всех изменений
    await db_session.rollback()
