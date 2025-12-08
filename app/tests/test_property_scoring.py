"""Tests for property scoring system."""
import pytest
from app.utils.property_scoring import PropertyScoringSystem, PropertyScore
from app.models.schemas import PropertyCreate


@pytest.fixture
def sample_property():
    """Create a sample property for testing."""
    return PropertyCreate(
        source="avito",
        external_id="test123",
        title="2-комнатная квартира",
        description="Отличная квартира в центре города с ремонтом",
        price=50000.0,
        rooms=2,
        area=60.0,
        city="Москва",
        district="Центр",
        photos=["photo1.jpg", "photo2.jpg", "photo3.jpg"],
        contact_phone="+79991234567",
        contact_name="Иван",
        is_verified=True
    )


class TestPropertyScoringSystem:
    """Tests for PropertyScoringSystem."""
    
    def test_calculate_score(self, sample_property):
        """Test score calculation."""
        score = PropertyScoringSystem.calculate_score(sample_property)
        
        assert isinstance(score, PropertyScore)
        assert 0 <= score.total <= 100
        assert 0 <= score.price_score <= 100
        assert 0 <= score.area_score <= 100
        assert 0 <= score.location_score <= 100
        assert 0 <= score.amenities_score <= 100
        assert 0 <= score.verification_score <= 100
    
    def test_price_score_calculation(self):
        """Test price score calculation."""
        # Below market average (good deal)
        score_low = PropertyScoringSystem._calculate_price_score(40000, 50000)
        assert score_low >= 90
        
        # At market average
        score_avg = PropertyScoringSystem._calculate_price_score(50000, 50000)
        assert 60 <= score_avg <= 80
        
        # Above market average
        score_high = PropertyScoringSystem._calculate_price_score(75000, 50000)
        assert score_high < 70
    
    def test_area_score_calculation(self):
        """Test area score calculation."""
        # Large area (good)
        score_large = PropertyScoringSystem._calculate_area_score(75, 50)
        assert score_large >= 80
        
        # Average area
        score_avg = PropertyScoringSystem._calculate_area_score(50, 50)
        assert 60 <= score_avg <= 80
        
        # Small area
        score_small = PropertyScoringSystem._calculate_area_score(30, 50)
        assert score_small < 60
    
    def test_location_score_moscow_center(self):
        """Test location score for Moscow center."""
        prop = PropertyCreate(
            source="test",
            external_id="1",
            title="Test",
            price=50000,
            city="Москва",
            district="Центр"
        )
        score = PropertyScoringSystem._calculate_location_score(prop)
        assert score >= 90
    
    def test_location_score_spb(self):
        """Test location score for Saint Petersburg."""
        prop = PropertyCreate(
            source="test",
            external_id="1",
            title="Test",
            price=50000,
            city="Санкт-Петербург",
            district="Невский"
        )
        score = PropertyScoringSystem._calculate_location_score(prop)
        assert score >= 80
    
    def test_amenities_score_full(self, sample_property):
        """Test amenities score with all features."""
        score = PropertyScoringSystem._calculate_amenities_score(sample_property)
        # Should have decent score with 3 photos (15), description (25), phone (10) and name (10) = 60
        assert score >= 50
    
    def test_amenities_score_minimal(self):
        """Test amenities score with minimal features."""
        prop = PropertyCreate(
            source="test",
            external_id="1",
            title="Test",
            price=50000
        )
        score = PropertyScoringSystem._calculate_amenities_score(prop)
        assert score < 30
    
    def test_rank_properties(self):
        """Test ranking multiple properties."""
        properties = [
            PropertyCreate(
                source="test",
                external_id="1",
                title="Expensive",
                price=100000,
                area=50,
                city="Москва"
            ),
            PropertyCreate(
                source="test",
                external_id="2",
                title="Good deal",
                price=40000,
                area=60,
                city="Москва",
                district="Центр",
                photos=["p1.jpg"],
                is_verified=True
            ),
            PropertyCreate(
                source="test",
                external_id="3",
                title="Average",
                price=50000,
                area=55,
                city="Москва"
            )
        ]
        
        ranked = PropertyScoringSystem.rank_properties(properties)
        
        assert len(ranked) == 3
        # Best deal should be ranked first
        assert ranked[0][0].external_id == "2"
        # Check scores are in descending order
        assert ranked[0][1].total >= ranked[1][1].total >= ranked[2][1].total
    
    def test_get_value_rating(self):
        """Test value rating conversion."""
        score_excellent = PropertyScore(90, 90, 90, 90, 90, 100)
        assert PropertyScoringSystem.get_value_rating(score_excellent) == "Отличное"
        
        score_good = PropertyScore(75, 70, 70, 70, 70, 100)
        assert PropertyScoringSystem.get_value_rating(score_good) == "Хорошее"
        
        score_average = PropertyScore(60, 60, 60, 60, 60, 50)
        assert PropertyScoringSystem.get_value_rating(score_average) == "Среднее"
        
        score_poor = PropertyScore(35, 30, 30, 30, 30, 50)
        assert PropertyScoringSystem.get_value_rating(score_poor) == "Плохое"
    
    def test_score_to_dict(self):
        """Test score serialization."""
        score = PropertyScore(85.5, 90.2, 80.7, 85.3, 75.8, 100.0)
        score_dict = score.to_dict()
        
        assert isinstance(score_dict, dict)
        assert score_dict["total"] == 85.5
        assert score_dict["price_score"] == 90.2
        assert all(isinstance(v, float) for v in score_dict.values())
    
    def test_verified_vs_unverified(self):
        """Test that verified properties get higher scores."""
        verified = PropertyCreate(
            source="test",
            external_id="1",
            title="Test",
            price=50000,
            area=50,
            city="Москва",
            is_verified=True
        )
        
        unverified = PropertyCreate(
            source="test",
            external_id="2",
            title="Test",
            price=50000,
            area=50,
            city="Москва",
            is_verified=False
        )
        
        score_verified = PropertyScoringSystem.calculate_score(verified)
        score_unverified = PropertyScoringSystem.calculate_score(unverified)
        
        assert score_verified.verification_score > score_unverified.verification_score
        assert score_verified.total > score_unverified.total
