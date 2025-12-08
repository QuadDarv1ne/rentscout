"""Tests for advanced search functionality."""
import pytest
from app.utils.advanced_search import (
    AdvancedSearchEngine,
    SearchFilter,
    SortOrder
)
from app.models.schemas import PropertyCreate


@pytest.fixture
def sample_properties():
    """Create sample properties for testing."""
    return [
        PropertyCreate(
            source="avito",
            external_id="1",
            title="2-комнатная квартира, 50 кв.м",
            price=50000.0,
            rooms=2,
            area=50.0,
            city="Москва",
            district="Центр",
            floor=3,
            total_floors=5,
            photos=["photo1.jpg"],
            description="Хорошая квартира",
            is_verified=True
        ),
        PropertyCreate(
            source="cian",
            external_id="2",
            title="3-комнатная квартира, 75 кв.м",
            price=75000.0,
            rooms=3,
            area=75.0,
            city="Москва",
            district="Юго-Запад",
            floor=2,
            total_floors=9,
            photos=["photo2.jpg", "photo3.jpg"],
            description="Новая квартира",
            is_verified=False
        ),
        PropertyCreate(
            source="domofond",
            external_id="3",
            title="1-комнатная квартира, 30 кв.м",
            price=30000.0,
            rooms=1,
            area=30.0,
            city="Санкт-Петербург",
            district="Невский",
            floor=5,
            total_floors=5,
            photos=[],
            description=None,
            is_verified=True
        ),
        PropertyCreate(
            source="avito",
            external_id="4",
            title="2-комнатная квартира, 52 кв.м",
            price=51000.0,
            rooms=2,
            area=52.0,
            city="Москва",
            district="Центр",
            floor=1,
            total_floors=10,
            photos=["photo4.jpg"],
            description="Похожая квартира на первую",
            is_verified=True
        ),
    ]


class TestSearchFilter:
    """Tests for SearchFilter."""
    
    def test_filter_by_price(self, sample_properties):
        """Test filtering by price."""
        filter = SearchFilter(min_price=40000, max_price=60000)
        filtered = [p for p in sample_properties if filter.matches(p)]
        
        assert len(filtered) == 3  # Properties 1, 2, 4
        assert all(40000 <= p.price <= 60000 for p in filtered)
    
    def test_filter_by_rooms(self, sample_properties):
        """Test filtering by rooms."""
        filter = SearchFilter(min_rooms=2, max_rooms=2)
        filtered = [p for p in sample_properties if filter.matches(p)]
        
        assert len(filtered) == 2  # Properties 1, 4
        assert all(p.rooms == 2 for p in filtered)
    
    def test_filter_by_area(self, sample_properties):
        """Test filtering by area."""
        filter = SearchFilter(min_area=45, max_area=60)
        filtered = [p for p in sample_properties if filter.matches(p)]
        
        assert len(filtered) == 2  # Properties 1, 4
        assert all(45 <= p.area <= 60 for p in filtered)
    
    def test_filter_by_city(self, sample_properties):
        """Test filtering by city."""
        filter = SearchFilter(cities=["Москва"])
        filtered = [p for p in sample_properties if filter.matches(p)]
        
        assert len(filtered) == 3  # Properties 1, 2, 4
        assert all(p.city == "Москва" for p in filtered)
    
    def test_filter_by_has_photos(self, sample_properties):
        """Test filtering by photos."""
        filter = SearchFilter(has_photos=True)
        filtered = [p for p in sample_properties if filter.matches(p)]
        
        assert len(filtered) == 3  # Properties 1, 2, 4 (3 has no photos)
        assert all(len(p.photos) > 0 for p in filtered)
    
    def test_filter_by_verified(self, sample_properties):
        """Test filtering by verification."""
        filter = SearchFilter(verified_only=True)
        filtered = [p for p in sample_properties if filter.matches(p)]
        
        assert len(filtered) == 3  # Properties 1, 3, 4
        assert all(p.is_verified for p in filtered)
    
    def test_filter_multiple_criteria(self, sample_properties):
        """Test filtering with multiple criteria."""
        filter = SearchFilter(
            min_price=40000,
            max_price=80000,
            min_rooms=2,
            cities=["Москва"],
            has_photos=True
        )
        filtered = [p for p in sample_properties if filter.matches(p)]
        
        assert len(filtered) == 2  # Properties 1, 4


class TestAdvancedSearchEngine:
    """Tests for AdvancedSearchEngine."""
    
    def test_filter_properties(self, sample_properties):
        """Test property filtering."""
        filter = SearchFilter(min_price=40000, max_price=80000)
        result = AdvancedSearchEngine.filter_properties(sample_properties, filter)
        
        assert len(result) == 3
        assert all(40000 <= p.price <= 80000 for p in result)
    
    def test_rank_by_price_asc(self, sample_properties):
        """Test ranking by price ascending."""
        result = AdvancedSearchEngine.rank_properties(
            sample_properties,
            sort_by="price",
            order=SortOrder.ASC
        )
        
        prices = [p.price for p in result]
        assert prices == sorted(prices)
    
    def test_rank_by_price_desc(self, sample_properties):
        """Test ranking by price descending."""
        result = AdvancedSearchEngine.rank_properties(
            sample_properties,
            sort_by="price",
            order=SortOrder.DESC
        )
        
        prices = [p.price for p in result]
        assert prices == sorted(prices, reverse=True)
    
    def test_rank_by_area(self, sample_properties):
        """Test ranking by area."""
        result = AdvancedSearchEngine.rank_properties(
            sample_properties,
            sort_by="area",
            order=SortOrder.ASC
        )
        
        areas = [p.area for p in result if p.area]
        assert areas == sorted(areas)
    
    def test_rank_by_price_per_area(self, sample_properties):
        """Test ranking by price per area."""
        result = AdvancedSearchEngine.rank_properties(
            sample_properties,
            sort_by="price_per_area",
            order=SortOrder.ASC
        )
        
        price_per_area = [p.price / p.area for p in result if p.area > 0]
        assert price_per_area == sorted(price_per_area)
    
    def test_deduplicate_properties(self, sample_properties):
        """Test deduplication."""
        # Add a duplicate
        duplicate = PropertyCreate(
            source="avito",
            external_id="1",  # Same as first property
            title="2-комнатная квартира, 50 кв.м",
            price=50000.0,
            rooms=2,
            area=50.0,
            city="Москва"
        )
        
        test_props = sample_properties + [duplicate]
        result = AdvancedSearchEngine.deduplicate_properties(test_props)
        
        assert len(result) == 4  # Duplicate removed
    
    def test_get_price_distribution(self, sample_properties):
        """Test price distribution."""
        result = AdvancedSearchEngine.get_price_distribution(
            sample_properties,
            bucket_count=5
        )
        
        assert result["count"] == 4
        assert result["min"] == 30000.0
        assert result["max"] == 75000.0
        assert result["avg"] > 0
        assert result["median"] > 0
        assert len(result["distribution"]) == 5
    
    def test_string_similarity(self):
        """Test string similarity calculation."""
        # Identical strings
        assert AdvancedSearchEngine._string_similarity("квартира", "квартира") == 1.0
        
        # Completely different strings
        assert AdvancedSearchEngine._string_similarity("дом", "автомобиль") < 0.5
        
        # Similar strings
        similarity = AdvancedSearchEngine._string_similarity(
            "2-комнатная квартира 50 м²",
            "2-комнатная квартира 51 м²"
        )
        assert similarity > 0.7


class TestIntegration:
    """Integration tests for advanced search."""
    
    def test_full_search_pipeline(self, sample_properties):
        """Test complete search pipeline."""
        # Filter
        filter = SearchFilter(
            min_price=40000,
            max_price=80000,
            min_rooms=2,
            cities=["Москва"]
        )
        filtered = AdvancedSearchEngine.filter_properties(sample_properties, filter)
        
        # Deduplicate
        unique = AdvancedSearchEngine.deduplicate_properties(filtered)
        
        # Rank
        ranked = AdvancedSearchEngine.rank_properties(
            unique,
            sort_by="price",
            order=SortOrder.ASC
        )
        
        assert len(ranked) == 2
        assert ranked[0].price <= ranked[1].price
    
    def test_empty_filter(self, sample_properties):
        """Test with empty filter."""
        filter = SearchFilter()
        result = AdvancedSearchEngine.filter_properties(sample_properties, filter)
        
        assert len(result) == len(sample_properties)
    
    def test_no_matching_properties(self, sample_properties):
        """Test with no matching properties."""
        filter = SearchFilter(min_price=1000000)  # Unrealistic price
        result = AdvancedSearchEngine.filter_properties(sample_properties, filter)
        
        assert len(result) == 0
