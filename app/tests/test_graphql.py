"""
Тесты для GraphQL API.
"""

import pytest

# Импортируем с проверкой доступности strawberry
try:
    from app.api.graphql import (
        PropertyType,
        PropertyFilter,
        HealthStatus,
        PropertyStatisticsType,
        Query,
        Mutation,
        STRAWBERRY_AVAILABLE,
    )
except ImportError:
    STRAWBERRY_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not STRAWBERRY_AVAILABLE,
    reason="Strawberry not installed"
)


class TestGraphQLTypes:
    """Тесты GraphQL типов."""

    def test_property_type_creation(self):
        """Тест создания типа PropertyType."""
        prop = PropertyType(
            id=1, source="avito", external_id="ext_1",
            title="Test", description="Nice",
            price=50000, rooms=2, area=54.5, floor=5,
            city="Москва", photos=[],
            is_active=True, created_at=None, last_seen=None,
            district=None, address=None,
            latitude=None, longitude=None
        )
        assert prop.id == 1
        assert prop.source == "avito"
        assert prop.price == 50000

    def test_property_filter_creation(self):
        """Тест создания фильтра."""
        f = PropertyFilter(
            city="Москва", min_price=30000,
            max_price=100000, min_rooms=1, max_rooms=3
        )
        assert f.city == "Москва"
        assert f.min_price == 30000

    def test_health_status_creation(self):
        """Тест HealthStatus."""
        from datetime import datetime
        status = HealthStatus(
            status="operational", version="1.0.0",
            timestamp=datetime.utcnow(),
            database="connected", cache="connected"
        )
        assert status.status == "operational"

    def test_statistics_type_creation(self):
        """Тест PropertyStatisticsType."""
        stats = PropertyStatisticsType(
            total=100, avg_price=55000,
            min_price=30000, max_price=100000,
            avg_area=50.5, min_area=20, max_area=150
        )
        assert stats.total == 100


class TestGraphQLQueries:
    """Тесты GraphQL queries."""

    def test_hello_query(self):
        """Тест hello query."""
        query = Query()
        result = query.hello()
        assert "Welcome" in result

    def test_health_query(self):
        """Тест health query."""
        query = Query()
        result = query.health()
        assert result.status == "operational"
        assert result.version == "1.0.0"

    def test_property_query(self):
        """Тест property query."""
        query = Query()
        result = query.property(id=1)
        assert result is not None
        assert result.id == 1

    def test_properties_query_no_filter(self):
        """Тест properties без фильтра."""
        query = Query()
        results = query.properties(limit=5, offset=0)
        assert len(results) == 5

    def test_properties_query_pagination(self):
        """Тест пагинации."""
        query = Query()
        page1 = query.properties(limit=5, offset=0)
        page2 = query.properties(limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5
        assert page1[0].id != page2[0].id

    def test_statistics_query(self):
        """Тест statistics query."""
        query = Query()
        result = query.statistics(city="Москва", days=30)
        assert result.total > 0


class TestGraphQLMutations:
    """Тесты GraphQL mutations."""

    def test_create_property_mutation(self):
        """Тест create_property."""
        mutation = Mutation()
        result = mutation.create_property(
            source="cian", external_id="new_123",
            title="New", price=60000, city="СПб"
        )
        assert result.source == "cian"
        assert result.price == 60000

    def test_update_property_mutation(self):
        """Тест update_property."""
        mutation = Mutation()
        result = mutation.update_property(id=1, price=55000)
        assert result.id == 1
        assert result.price == 55000

    def test_delete_property_mutation(self):
        """Тест delete_property."""
        mutation = Mutation()
        result = mutation.delete_property(id=1)
        assert result is True


class TestGraphQLSchema:
    """Тесты GraphQL схемы."""

    def test_schema_creation(self):
        """Тест создания схемы."""
        from app.api.graphql import schema
        assert schema is not None

    def test_graphql_router_import(self):
        """Тест импорта router."""
        from app.api.graphql import graphql_app
        assert graphql_app is not None


class TestGraphQLIntegration:
    """Интеграционные тесты."""

    def test_full_query_workflow(self):
        """Тест workflow query."""
        query = Query()
        health = query.health()
        assert health.status == "operational"
        props = query.properties(limit=3)
        assert len(props) == 3

    def test_full_mutation_workflow(self):
        """Тест workflow mutation."""
        mutation = Mutation()
        created = mutation.create_property(
            source="avito", external_id="t1",
            title="T", price=50000, city="М"
        )
        assert created is not None
        updated = mutation.update_property(id=created.id, price=55000)
        assert updated.price == 55000
        deleted = mutation.delete_property(id=created.id)
        assert deleted is True
