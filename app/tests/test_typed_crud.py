"""
Тесты для типизированных CRUD операций.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.models.schemas import PropertyCreate
from app.schemas.db_responses import (
    PropertyResponse,
    PropertiesListResponse,
    BulkUpsertResponse,
    PropertyStatistics,
)


class TestPropertyResponse:
    """Тесты схемы ответа Property."""

    def test_property_response_creation(self):
        """Тест создания ответа."""
        response = PropertyResponse(
            id=1,
            source="avito",
            external_id="123456",
            title="2-комнатная квартира",
            price=50000,
            rooms=2,
            area=54.5,
            city="Москва",
        )
        assert response.id == 1
        assert response.source == "avito"
        assert response.price == 50000

    def test_property_response_from_model(self):
        """Тест создания из модели."""
        # Создаем мок объекта Property с правильными атрибутами
        mock_property = MagicMock()
        mock_property.id = 1
        mock_property.source = "cian"
        mock_property.external_id = "789"
        mock_property.title = "Studio"
        mock_property.price = 35000
        mock_property.rooms = 0
        mock_property.area = 25.0
        mock_property.city = "Санкт-Петербург"
        mock_property.is_active = True
        mock_property.created_at = datetime.utcnow()
        # Optional fields - set to None or proper types
        mock_property.description = None
        mock_property.link = None
        mock_property.currency = "RUB"
        mock_property.district = None
        mock_property.address = None
        mock_property.location = {}
        mock_property.features = None
        mock_property.contact_name = None
        mock_property.contact_phone = None
        mock_property.last_seen = None
        mock_property.last_updated = None
        mock_property.photos = []

        response = PropertyResponse.model_validate(mock_property)
        assert response.source == "cian"
        assert response.price == 35000


class TestPropertiesListResponse:
    """Тесты схемы списка свойств."""

    def test_paginated_response_creation(self):
        """Тест создания пагинированного ответа."""
        items = [
            PropertyResponse(
                id=1, source="avito", external_id="1",
                title="Flat", price=50000, city="Москва"
            ),
            PropertyResponse(
                id=2, source="cian", external_id="2",
                title="Studio", price=35000, city="Москва"
            ),
        ]

        response = PropertiesListResponse(
            items=items,
            total=100,
            skip=0,
            limit=2,
            page=1,
            pages=50,
            has_next=True,
            has_prev=False,
        )

        assert response.total == 100
        assert response.has_next is True
        assert response.has_prev is False

    def test_paginated_response_create_helper(self):
        """Тест хелпера создания пагинации."""
        from app.schemas.db_responses import PaginatedResponse

        response = PaginatedResponse.create(
            items=[1, 2, 3],
            total=100,
            skip=0,
            limit=10,
        )

        assert response.page == 1
        assert response.pages == 10
        assert response.has_next is True


class TestBulkUpsertResponse:
    """Тесты массовых операций."""

    def test_bulk_upsert_success(self):
        """Тест успешной массовой операции."""
        response = BulkUpsertResponse(
            success=True,
            created=10,
            updated=5,
            errors=0,
            processing_time_ms=150.5,
        )

        assert response.success is True
        assert response.created == 10
        assert response.errors == 0

    def test_bulk_upsert_error(self):
        """Тест ошибочной массовой операции."""
        response = BulkUpsertResponse(
            success=False,
            created=0,
            errors=10,
            error_details=[{"error": "Database connection failed"}],
        )

        assert response.success is False
        assert response.errors == 10


class TestPropertyStatistics:
    """Тесты статистики."""

    def test_statistics_creation(self):
        """Тест создания статистики."""
        stats = PropertyStatistics(
            total=100,
            avg_price=55000.0,
            min_price=30000.0,
            max_price=100000.0,
            avg_area=45.5,
        )

        assert stats.total == 100
        assert stats.avg_price == 55000.0

    def test_statistics_with_nulls(self):
        """Тест статистики с null значениями."""
        stats = PropertyStatistics(
            total=0,
            avg_price=None,
            min_price=None,
            max_price=None,
        )

        assert stats.total == 0
        assert stats.avg_price is None


class TestPropertyCRUD:
    """Тесты CRUD операций (mock)."""

    @pytest.fixture
    def mock_db_session(self):
        """Фикстура мок сессии БД."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def sample_property_data(self):
        """Фикстура тестовых данных."""
        return PropertyCreate(
            source="avito",
            external_id="123456",
            title="2-комнатная квартира",
            price=50000,
            rooms=2,
            area=54.5,
            city="Москва",
        )

    @pytest.mark.asyncio
    async def test_create_property(self, mock_db_session, sample_property_data):
        """Тест создания свойства."""
        from app.db.typed_crud import PropertyCRUD

        # Мок для flush и refresh
        mock_db_session.flush.return_value = None
        mock_db_session.refresh.return_value = None

        # Мок для созданного объекта
        created_property = MagicMock()
        created_property.id = 1
        created_property.source = "avito"
        created_property.price = 50000

        # Настраиваем mock так чтобы после flush/refres свойство имело id
        async def mock_flush():
            mock_db_session.add.call_args[0][0].id = 1
        mock_db_session.flush = mock_flush

        async def mock_refresh(obj):
            obj.id = 1

        mock_db_session.refresh = mock_refresh

        with patch('app.db.typed_crud.PropertyResponse.model_validate') as mock_validate:
            mock_validate.return_value = PropertyResponse(
                id=1,
                source="avito",
                external_id="123456",
                title="2-комнатная квартира",
                price=50000,
                city="Москва",
            )

            result = await PropertyCRUD.create(mock_db_session, sample_property_data)

            assert isinstance(result, PropertyResponse)
            assert result.source == "avito"
            assert result.price == 50000

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, mock_db_session):
        """Тест получения по ID (найдено)."""
        from app.db.typed_crud import PropertyCRUD

        mock_property = MagicMock()
        mock_property.id = 1
        mock_property.source = "cian"
        mock_property.price = 40000

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_property
        mock_db_session.execute.return_value = mock_result

        with patch('app.db.typed_crud.PropertyResponse.model_validate') as mock_validate:
            mock_validate.return_value = PropertyResponse(
                id=1, source="cian", external_id="789",
                title="Flat", price=40000, city="СПб"
            )

            result = await PropertyCRUD.get_by_id(mock_db_session, 1)

            assert result is not None
            assert result.source == "cian"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_db_session):
        """Тест получения по ID (не найдено)."""
        from app.db.typed_crud import PropertyCRUD

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await PropertyCRUD.get_by_id(mock_db_session, 999)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_success(self, mock_db_session):
        """Тест успешного удаления."""
        from app.db.typed_crud import PropertyCRUD

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result

        result = await PropertyCRUD.delete(mock_db_session, 1)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_db_session):
        """Тест удаления несуществующего."""
        from app.db.typed_crud import PropertyCRUD

        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db_session.execute.return_value = mock_result

        result = await PropertyCRUD.delete(mock_db_session, 999)

        assert result is False


class TestErrorResponse:
    """Тесты схем ошибок."""

    def test_error_response_creation(self):
        """Тест создания ответа об ошибке."""
        from app.schemas.db_responses import ErrorResponse

        error = ErrorResponse(
            error="not_found",
            message="Property not found",
            request_id="req-123",
        )

        assert error.error == "not_found"
        assert error.request_id == "req-123"

    def test_validation_error_response(self):
        """Тест ответа с ошибками валидации."""
        from app.schemas.db_responses import (
            ValidationErrorResponse,
            ValidationErrorDetail,
        )

        error = ValidationErrorResponse(
            message="Validation failed",
            details=[
                ValidationErrorDetail(
                    loc=["body", "price"],
                    msg="Field required",
                    type="value_error.missing",
                )
            ],
        )

        assert error.error == "validation_error"
        assert len(error.details) == 1
        assert error.details[0].loc == ["body", "price"]


class TestSearchQueryParams:
    """Тесты параметров поиска."""

    def test_search_params_creation(self):
        """Тест создания параметров поиска."""
        from app.schemas.db_responses import SearchQueryParams

        params = SearchQueryParams(
            city="Москва",
            min_price=30000,
            max_price=100000,
            min_rooms=1,
        )

        assert params.city == "Москва"
        assert params.min_price == 30000

    def test_search_params_validation(self):
        """Тест валидации параметров поиска."""
        from app.schemas.db_responses import SearchQueryParams
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            SearchQueryParams(city="М")  # Слишком короткий

        with pytest.raises(ValidationError):
            SearchQueryParams(min_price=-1000)  # Отрицательная цена
