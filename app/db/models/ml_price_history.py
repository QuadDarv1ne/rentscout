"""
SQLAlchemy model for ML price prediction history.
Stores historical price data for ML model training and trend analysis.
"""
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class MLPriceHistory(Base):
    """Store historical price data for ML model analysis."""
    
    __tablename__ = "ml_price_history"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # City identifier (required for city-based coefficients)
    city = Column(String(100), nullable=False, index=True)
    
    # Price data
    price = Column(Float, nullable=False, index=True)  # Indexed for faster queries
    
    # Property characteristics
    rooms = Column(Integer, index=True)  # Indexed for room-based queries
    area = Column(Float, index=True)  # Square meters - indexed for area-based queries
    district = Column(String(100), index=True)  # Indexed for district-based queries
    floor = Column(Integer, index=True)  # Indexed for floor-based queries
    total_floors = Column(Integer)
    
    # Source information
    source = Column(String(50), nullable=True, index=True)  # avito, cian, etc. - indexed
    external_id = Column(String(255), nullable=True)  # Link to original property
    
    # Property type and verification
    property_type = Column(String(50), default="apartment", index=True)  # apartment, house, etc. - indexed
    is_verified = Column(Integer, default=0, index=True)  # Boolean: 0 or 1 for compatibility - indexed
    
    # Timestamp (when this price was recorded)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Metadata for filtering
    currency = Column(String(10), default="RUB")
    is_active = Column(Integer, default=1, index=True)  # 1 = active, 0 = inactive listing - indexed
    
    # Indexes for performance
    __table_args__ = (
        # Composite index for city and time-based queries
        Index('ix_city_recorded', 'city', 'recorded_at'),
        
        # Index for trend analysis by city and rooms
        Index('ix_city_rooms_recorded', 'city', 'rooms', 'recorded_at'),
        
        # Index for area-based queries
        Index('ix_city_area_recorded', 'city', 'area', 'recorded_at'),
        
        # Index for district analysis
        Index('ix_district_recorded', 'district', 'recorded_at'),
        
        # Index for time-series queries
        Index('ix_recorded_at', 'recorded_at'),
        
        # Index for active listings
        Index('ix_is_active_recorded', 'is_active', 'recorded_at'),
        
        # Additional indexes for enhanced performance
        Index('ix_price_rooms', 'price', 'rooms'),  # For price and room correlation analysis
        Index('ix_area_price', 'area', 'price'),  # For area and price correlation analysis
        Index('ix_source_recorded', 'source', 'recorded_at'),  # For source-based time analysis
        Index('ix_verified_recorded', 'is_verified', 'recorded_at'),  # For verification-based analysis
        Index('ix_floor_recorded', 'floor', 'recorded_at'),  # For floor-based analysis
        Index('ix_city_district_recorded', 'city', 'district', 'recorded_at'),  # For city-district analysis
        Index('ix_price_per_sqm', 'price', 'area'),  # For price per square meter calculations
    )
    
    def __repr__(self):
        return f"<MLPriceHistory(city={self.city}, price={self.price}, rooms={self.rooms}, recorded_at={self.recorded_at})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'city': self.city,
            'price': self.price,
            'rooms': self.rooms,
            'area': self.area,
            'district': self.district,
            'floor': self.floor,
            'total_floors': self.total_floors,
            'source': self.source,
            'external_id': self.external_id,
            'property_type': self.property_type,
            'is_verified': bool(self.is_verified),
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
            'currency': self.currency,
            'is_active': bool(self.is_active),
        }