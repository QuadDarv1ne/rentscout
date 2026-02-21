"""
SQLAlchemy models for property data persistence.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Float, Integer, DateTime, Boolean, JSON, Index, UniqueConstraint, Text
from sqlalchemy.orm import declarative_base
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
    description = Column(Text)  # Changed to Text for better performance with long descriptions
    link = Column(String(1000))
    
    # Price information
    price = Column(Float, nullable=False, index=True)
    currency = Column(String(10), default="RUB")
    price_per_sqm = Column(Float, index=True)  # Price per square meter - indexed for faster queries
    
    # Property characteristics
    rooms = Column(Integer, index=True)  # Indexed for room-based queries
    area = Column(Float, index=True)  # Total area in square meters - indexed
    floor = Column(Integer, index=True)  # Indexed for floor-based queries
    total_floors = Column(Integer)
    
    # Location
    city = Column(String(100), index=True)
    district = Column(String(100), index=True)  # Indexed for district-based queries
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
    is_verified = Column(Boolean, default=False, index=True)  # Indexed for verification-based queries
    
    # Timestamps
    first_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)  # Indexed
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, index=True)  # Indexed
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)  # Indexed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
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
        
        # New indexes for enhanced query performance
        Index('ix_price_per_sqm', 'price_per_sqm'),  # For price per square meter queries
        Index('ix_rooms_price', 'rooms', 'price'),  # For room and price combination queries
        Index('ix_city_district', 'city', 'district'),  # For city and district combination queries
        Index('ix_verified_active', 'is_verified', 'is_active'),  # For verified and active properties
        Index('ix_area_price_per_sqm', 'area', 'price_per_sqm'),  # For area and price per sqm queries
        Index('ix_source_first_seen', 'source', 'first_seen'),  # For source and first seen queries
        Index('ix_floor_total_floors', 'floor', 'total_floors'),  # For floor-related queries
    )
    
    def __repr__(self):
        return f"<Property(id={self.id}, source={self.source}, external_id={self.external_id}, title={self.title[:30]}...)>"

    def to_dict(self):
        """Convert property to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'source': self.source,
            'external_id': self.external_id,
            'title': self.title,
            'description': self.description,
            'link': self.link,
            'price': self.price,
            'currency': self.currency,
            'price_per_sqm': self.price_per_sqm,
            'rooms': self.rooms,
            'area': self.area,
            'floor': self.floor,
            'total_floors': self.total_floors,
            'city': self.city,
            'district': self.district,
            'address': self.address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'location': self.location,
            'photos': self.photos,
            'features': self.features,
            'contact_name': self.contact_name,
            'contact_phone': self.contact_phone,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


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
    changed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)  # Indexed
    
    __table_args__ = (
        Index('ix_property_changed', 'property_id', 'changed_at'),
        Index('ix_changed_at', 'changed_at'),  # For time-based queries
        Index('ix_price_change', 'price_change'),  # For price change analysis
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
    viewed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)  # Indexed
    
    __table_args__ = (
        Index('ix_property_viewed', 'property_id', 'viewed_at'),
        Index('ix_ip_viewed', 'ip_address', 'viewed_at'),
        Index('ix_viewed_at', 'viewed_at'),  # For time-based analytics
    )
    
    def __repr__(self):
        return f"<PropertyView(property_id={self.property_id}, viewed_at={self.viewed_at})>"


class SearchQuery(Base):
    """Track user search queries for analytics and recommendations."""
    
    __tablename__ = "search_queries"
    
    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(100), index=True)
    property_type = Column(String(50), index=True)  # Indexed for property type queries
    
    # Search criteria
    max_price = Column(Float, index=True)  # Indexed for price-based queries
    min_price = Column(Float, index=True)  # Indexed for price-based queries
    rooms = Column(Integer, index=True)  # Indexed for room-based queries
    min_area = Column(Float, index=True)  # Indexed for area-based queries
    max_area = Column(Float, index=True)  # Indexed for area-based queries
    
    # Results
    results_count = Column(Integer, default=0)
    
    # User info
    ip_address = Column(String(45))  # IPv4 or IPv6
    
    # Timestamp
    searched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)  # Indexed
    
    __table_args__ = (
        Index('ix_city_searched', 'city', 'searched_at'),
        Index('ix_ip_searched', 'ip_address', 'searched_at'),
        Index('ix_searched_at', 'searched_at'),  # For time-based analytics
        Index('ix_city_property_type', 'city', 'property_type'),  # For city and property type queries
        Index('ix_price_range', 'min_price', 'max_price'),  # For price range queries
    )
    
    def __repr__(self):
        return f"<SearchQuery(city={self.city}, type={self.property_type}, results={self.results_count})>"


class PropertyAlert(Base):
    """Property alert for notifying users about new listings."""
    
    __tablename__ = "property_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    city = Column(String(100), nullable=False, index=True)
    
    # Alert criteria
    max_price = Column(Float, index=True)  # Indexed for price-based queries
    min_price = Column(Float, index=True)  # Indexed for price-based queries
    rooms = Column(Integer, index=True)  # Indexed for room-based queries
    min_area = Column(Float, index=True)  # Indexed for area-based queries
    max_area = Column(Float, index=True)  # Indexed for area-based queries
    
    # Notification settings
    email = Column(String(255), nullable=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)  # Indexed
    last_notified = Column(DateTime(timezone=True), index=True)  # Indexed for notification queries
    
    __table_args__ = (
        Index('ix_alert_city_active', 'city', 'is_active'),
        Index('ix_alert_email_active', 'email', 'is_active'),
        Index('ix_alert_created_at', 'created_at'),
        Index('ix_alert_price_range', 'min_price', 'max_price'),  # For price range queries
        Index('ix_alert_area_range', 'min_area', 'max_area'),  # For area range queries
        Index('ix_alert_last_notified', 'last_notified'),  # For notification timing queries
    )
    
    def __repr__(self):
        return f"<PropertyAlert(city={self.city}, email={self.email}, active={self.is_active})>"