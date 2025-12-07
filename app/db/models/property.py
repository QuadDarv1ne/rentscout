"""
SQLAlchemy models for property data persistence.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, JSON, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class Property(Base):
    """Property model for storing parsed property data."""
    
    __tablename__ = "properties"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # External identifiers
    source = Column(String(50), nullable=False, index=True)  # avito, cian, etc.
    external_id = Column(String(255), nullable=False)  # ID from source
    
    # Basic information
    title = Column(String(500), nullable=False)
    description = Column(String(5000))
    link = Column(String(1000))
    
    # Price information
    price = Column(Float, nullable=False, index=True)
    currency = Column(String(10), default="RUB")
    price_per_sqm = Column(Float)  # Price per square meter
    
    # Property characteristics
    rooms = Column(Integer)
    area = Column(Float)  # Total area in square meters
    floor = Column(Integer)
    total_floors = Column(Integer)
    
    # Location
    city = Column(String(100), index=True)
    district = Column(String(100))
    address = Column(String(500))
    latitude = Column(Float)
    longitude = Column(Float)
    location = Column(JSON)  # Full location data
    
    # Media
    photos = Column(JSON)  # List of photo URLs
    
    # Additional features
    features = Column(JSON)  # Amenities, utilities, etc.
    
    # Contact information
    contact_name = Column(String(200))
    contact_phone = Column(String(50))
    
    # Status tracking
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    first_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes for performance
    __table_args__ = (
        # Unique constraint for source + external_id
        UniqueConstraint('source', 'external_id', name='uix_source_external_id'),
        
        # Composite indexes for common queries
        Index('ix_city_price', 'city', 'price'),
        Index('ix_source_city', 'source', 'city'),
        Index('ix_active_price', 'is_active', 'price'),
        Index('ix_rooms_area', 'rooms', 'area'),
        
        # Additional indexes for performance optimization
        Index('ix_created_at', 'created_at'),
        Index('ix_last_seen', 'last_seen'),
        Index('ix_is_active_created', 'is_active', 'created_at'),
        Index('ix_source_is_active', 'source', 'is_active'),
        Index('ix_district', 'district'),
        Index('ix_price_area', 'price', 'area'),
        Index('ix_source_price', 'source', 'price'),
    )
    
    def __repr__(self):
        return f"<Property(id={self.id}, source={self.source}, external_id={self.external_id}, title={self.title[:30]}...)>"


class PropertyPriceHistory(Base):
    """Track price changes over time."""
    
    __tablename__ = "property_price_history"
    
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, nullable=False, index=True)
    
    # Price data
    old_price = Column(Float)
    new_price = Column(Float, nullable=False)
    price_change = Column(Float)  # Calculated: new_price - old_price
    price_change_percent = Column(Float)  # Calculated percentage
    
    # Timestamp
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_property_changed', 'property_id', 'changed_at'),
    )
    
    def __repr__(self):
        return f"<PropertyPriceHistory(property_id={self.property_id}, old={self.old_price}, new={self.new_price})>"


class PropertyView(Base):
    """Track property views for analytics."""
    
    __tablename__ = "property_views"
    
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, nullable=False, index=True)
    
    # View metadata
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(String(500))
    referer = Column(String(1000))
    
    # Timestamp
    viewed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_property_viewed', 'property_id', 'viewed_at'),
        Index('ix_ip_viewed', 'ip_address', 'viewed_at'),
    )
    
    def __repr__(self):
        return f"<PropertyView(property_id={self.property_id}, viewed_at={self.viewed_at})>"


class SearchQuery(Base):
    """Track user search queries for analytics and recommendations."""
    
    __tablename__ = "search_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Query parameters
    city = Column(String(100), index=True)
    property_type = Column(String(50))
    min_price = Column(Float)
    max_price = Column(Float)
    min_rooms = Column(Integer)
    max_rooms = Column(Integer)
    min_area = Column(Float)
    max_area = Column(Float)
    query_params = Column(JSON)  # Full query parameters
    
    # Results metadata
    results_count = Column(Integer)
    
    # User metadata
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    
    # Timestamp
    searched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_city_searched', 'city', 'searched_at'),
        Index('ix_ip_searched', 'ip_address', 'searched_at'),
    )
    
    def __repr__(self):
        return f"<SearchQuery(city={self.city}, type={self.property_type}, results={self.results_count})>"
