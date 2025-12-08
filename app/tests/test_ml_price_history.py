"""
Tests for ML price history repository and database integration.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models.ml_price_history import MLPriceHistory, Base
from app.db.repositories.ml_price_history import MLPriceHistoryRepository


# Use in-memory SQLite for testing
@pytest.fixture
def test_db():
    """Create test database."""
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


class TestMLPriceHistoryRepository:
    """Test CRUD operations for ML price history."""
    
    def test_add_price(self, test_db):
        """Test adding a price record."""
        record = MLPriceHistoryRepository.add_price(
            test_db,
            city="Москва",
            price=50000.0,
            rooms=2,
            area=45.0,
        )
        
        assert record.id is not None
        assert record.city == "Москва"
        assert record.price == 50000.0
        assert record.rooms == 2
    
    def test_add_price_with_all_fields(self, test_db):
        """Test adding price with all optional fields."""
        record = MLPriceHistoryRepository.add_price(
            test_db,
            city="Санкт-Петербург",
            price=45000.0,
            rooms=1,
            area=35.0,
            district="Центр",
            floor=5,
            total_floors=10,
            source="avito",
            external_id="avito_123",
            property_type="apartment",
            is_verified=True,
            is_active=True,
        )
        
        assert record.district == "Центр"
        assert record.floor == 5
        assert record.is_verified == 1
        assert record.is_active == 1
    
    def test_get_by_city(self, test_db):
        """Test retrieving prices by city."""
        # Add multiple records
        for i in range(5):
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=50000.0 + (i * 1000),
                rooms=2,
                area=45.0,
            )
        
        # Add records for different city
        MLPriceHistoryRepository.add_price(
            test_db,
            city="Казань",
            price=30000.0,
            rooms=2,
        )
        
        # Get Moscow records
        records = MLPriceHistoryRepository.get_by_city(test_db, "Москва")
        assert len(records) == 5
        assert all(r.city == "Москва" for r in records)
    
    def test_get_by_city_with_room_filter(self, test_db):
        """Test filtering by city and rooms."""
        # Add records with different rooms
        for rooms in [1, 2, 2, 3]:
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=50000.0,
                rooms=rooms,
            )
        
        # Get 2-room apartments
        records = MLPriceHistoryRepository.get_by_city(
            test_db,
            "Москва",
            rooms=2,
        )
        assert len(records) == 2
        assert all(r.rooms == 2 for r in records)
    
    def test_get_by_district(self, test_db):
        """Test retrieving by district."""
        # Add records for different districts
        for district in ["Центр", "Центр", "Периферия"]:
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=50000.0,
                district=district,
            )
        
        records = MLPriceHistoryRepository.get_by_district(
            test_db,
            "Москва",
            "Центр",
        )
        assert len(records) == 2
        assert all(r.district == "Центр" for r in records)
    
    def test_get_statistics(self, test_db):
        """Test statistics calculation."""
        # Add records with known prices
        prices = [40000, 50000, 60000, 55000, 45000]
        for price in prices:
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=float(price),
                rooms=2,
            )
        
        stats = MLPriceHistoryRepository.get_statistics(
            test_db,
            "Москва",
            rooms=2,
        )
        
        assert stats['count'] == 5
        assert stats['min_price'] == 40000
        assert stats['max_price'] == 60000
        assert stats['avg_price'] == 50000.0
        assert 'std_dev' in stats
    
    def test_get_statistics_empty(self, test_db):
        """Test statistics for non-existent city."""
        stats = MLPriceHistoryRepository.get_statistics(
            test_db,
            "NonExistentCity",
        )
        
        assert stats['count'] == 0
    
    def test_get_trend(self, test_db):
        """Test trend analysis."""
        # Add records with growing trend
        base_time = datetime.utcnow() - timedelta(days=30)
        
        # First half - lower prices
        for i in range(5):
            record = MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=45000.0,
                rooms=2,
            )
            # Manually set recorded_at for testing
            from sqlalchemy import update
            test_db.execute(
                update(MLPriceHistory)
                .where(MLPriceHistory.id == record.id)
                .values(recorded_at=base_time + timedelta(days=i))
            )
        
        # Second half - higher prices
        for i in range(5, 10):
            record = MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=55000.0,
                rooms=2,
            )
            from sqlalchemy import update
            test_db.execute(
                update(MLPriceHistory)
                .where(MLPriceHistory.id == record.id)
                .values(recorded_at=base_time + timedelta(days=i))
            )
        
        test_db.commit()
        
        trend = MLPriceHistoryRepository.get_trend(
            test_db,
            "Москва",
            rooms=2,
            days=30,
        )
        
        assert trend['samples'] == 10
        assert trend['change_percent'] > 0
        assert trend['trend'] == 'increasing'
    
    def test_get_trend_stable(self, test_db):
        """Test stable trend detection."""
        # Add records with stable prices
        for i in range(10):
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=50000.0,
                rooms=2,
            )
        
        trend = MLPriceHistoryRepository.get_trend(
            test_db,
            "Москва",
            rooms=2,
        )
        
        assert trend['trend'] == 'stable'
        assert abs(trend['change_percent']) <= 2
    
    def test_delete_old_records(self, test_db):
        """Test deleting old records."""
        # Add recent record
        MLPriceHistoryRepository.add_price(
            test_db,
            city="Москва",
            price=50000.0,
        )
        
        # Add old record
        old_record = MLPriceHistoryRepository.add_price(
            test_db,
            city="Москва",
            price=45000.0,
        )
        
        # Set old date
        from sqlalchemy import update
        test_db.execute(
            update(MLPriceHistory)
            .where(MLPriceHistory.id == old_record.id)
            .values(recorded_at=datetime.utcnow() - timedelta(days=400))
        )
        test_db.commit()
        
        # Delete records older than 365 days
        deleted = MLPriceHistoryRepository.delete_old_records(test_db, days=365)
        
        assert deleted >= 1
    
    def test_get_total_count(self, test_db):
        """Test getting total count."""
        for i in range(3):
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=50000.0,
            )
        
        count = MLPriceHistoryRepository.get_total_count(test_db)
        assert count == 3
    
    def test_get_city_count(self, test_db):
        """Test getting count by city."""
        for i in range(3):
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=50000.0,
            )
        
        for i in range(2):
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Казань",
                price=30000.0,
            )
        
        moscow_count = MLPriceHistoryRepository.get_city_count(test_db, "Москва")
        kazan_count = MLPriceHistoryRepository.get_city_count(test_db, "Казань")
        
        assert moscow_count == 3
        assert kazan_count == 2


class TestMLPriceHistoryModel:
    """Test MLPriceHistory model."""
    
    def test_model_creation(self, test_db):
        """Test creating a model instance."""
        record = MLPriceHistory(
            city="Москва",
            price=50000.0,
            rooms=2,
            area=45.0,
        )
        test_db.add(record)
        test_db.commit()
        
        assert record.id is not None
        assert record.city == "Москва"
    
    def test_model_to_dict(self, test_db):
        """Test converting model to dictionary."""
        record = MLPriceHistory(
            city="Москва",
            price=50000.0,
            rooms=2,
            area=45.0,
            is_verified=1,
        )
        test_db.add(record)
        test_db.commit()
        test_db.refresh(record)
        
        data = record.to_dict()
        
        assert data['city'] == "Москва"
        assert data['price'] == 50000.0
        assert data['rooms'] == 2
        assert data['is_verified'] is True
        assert 'recorded_at' in data
    
    def test_model_repr(self, test_db):
        """Test string representation."""
        record = MLPriceHistory(
            city="Москва",
            price=50000.0,
            rooms=2,
        )
        test_db.add(record)
        test_db.commit()
        
        repr_str = repr(record)
        assert "Москва" in repr_str
        assert "50000" in repr_str


class TestMLPriceHistoryIntegration:
    """Integration tests for ML price history."""
    
    def test_add_and_retrieve_workflow(self, test_db):
        """Test complete add and retrieve workflow."""
        # Add prices
        for i in range(10):
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=50000.0 + (i * 500),
                rooms=2,
                area=45.0,
            )
        
        # Retrieve and verify
        records = MLPriceHistoryRepository.get_by_city(test_db, "Москва")
        assert len(records) == 10
        
        # Calculate statistics
        stats = MLPriceHistoryRepository.get_statistics(test_db, "Москва")
        assert stats['count'] == 10
        assert stats['min_price'] == 50000.0
        assert stats['max_price'] == 54500.0
    
    def test_multiple_cities_isolation(self, test_db):
        """Test data isolation between cities."""
        for i in range(5):
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Москва",
                price=50000.0,
            )
            MLPriceHistoryRepository.add_price(
                test_db,
                city="Казань",
                price=30000.0,
            )
        
        moscow_records = MLPriceHistoryRepository.get_by_city(test_db, "Москва")
        kazan_records = MLPriceHistoryRepository.get_by_city(test_db, "Казань")
        
        assert len(moscow_records) == 5
        assert len(kazan_records) == 5
        assert all(r.price == 50000.0 for r in moscow_records)
        assert all(r.price == 30000.0 for r in kazan_records)
