"""Optimize database indexes and columns

Revision ID: optimize_indexes_001
Revises: 82868aac266e
Create Date: 2025-12-11 14:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'optimize_indexes_001'
down_revision: Union[str, None] = '82868aac266e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Upgrade properties table
    # Add indexes for better query performance
    op.create_index('ix_properties_price_per_sqm', 'properties', ['price_per_sqm'])
    op.create_index('ix_properties_rooms', 'properties', ['rooms'])
    op.create_index('ix_properties_area', 'properties', ['area'])
    op.create_index('ix_properties_floor', 'properties', ['floor'])
    op.create_index('ix_properties_is_verified', 'properties', ['is_verified'])
    op.create_index('ix_properties_first_seen', 'properties', ['first_seen'])
    op.create_index('ix_properties_last_updated', 'properties', ['last_updated'])
    
    # Add composite indexes for common query patterns
    op.create_index('ix_properties_rooms_price', 'properties', ['rooms', 'price'])
    op.create_index('ix_properties_city_district', 'properties', ['city', 'district'])
    op.create_index('ix_properties_verified_active', 'properties', ['is_verified', 'is_active'])
    op.create_index('ix_properties_area_price_per_sqm', 'properties', ['area', 'price_per_sqm'])
    op.create_index('ix_properties_source_first_seen', 'properties', ['source', 'first_seen'])
    op.create_index('ix_properties_floor_total_floors', 'properties', ['floor', 'total_floors'])
    
    # Upgrade property_price_history table
    op.create_index('ix_property_price_history_changed_at', 'property_price_history', ['changed_at'])
    op.create_index('ix_property_price_history_price_change', 'property_price_history', ['price_change'])
    
    # Upgrade property_views table
    op.create_index('ix_property_views_viewed_at', 'property_views', ['viewed_at'])
    
    # Upgrade search_queries table
    op.create_index('ix_search_queries_property_type', 'search_queries', ['property_type'])
    op.create_index('ix_search_queries_max_price', 'search_queries', ['max_price'])
    op.create_index('ix_search_queries_min_price', 'search_queries', ['min_price'])
    op.create_index('ix_search_queries_rooms', 'search_queries', ['rooms'])
    op.create_index('ix_search_queries_min_area', 'search_queries', ['min_area'])
    op.create_index('ix_search_queries_max_area', 'search_queries', ['max_area'])
    op.create_index('ix_search_queries_searched_at', 'search_queries', ['searched_at'])
    op.create_index('ix_search_queries_city_property_type', 'search_queries', ['city', 'property_type'])
    op.create_index('ix_search_queries_price_range', 'search_queries', ['min_price', 'max_price'])
    
    # Upgrade property_alerts table
    op.create_index('ix_property_alerts_max_price', 'property_alerts', ['max_price'])
    op.create_index('ix_property_alerts_min_price', 'property_alerts', ['min_price'])
    op.create_index('ix_property_alerts_rooms', 'property_alerts', ['rooms'])
    op.create_index('ix_property_alerts_min_area', 'property_alerts', ['min_area'])
    op.create_index('ix_property_alerts_max_area', 'property_alerts', ['max_area'])
    op.create_index('ix_property_alerts_created_at', 'property_alerts', ['created_at'])
    op.create_index('ix_property_alerts_last_notified', 'property_alerts', ['last_notified'])
    op.create_index('ix_property_alerts_price_range', 'property_alerts', ['min_price', 'max_price'])
    op.create_index('ix_property_alerts_area_range', 'property_alerts', ['min_area', 'max_area'])
    
    # Upgrade ml_price_history table
    op.create_index('ix_ml_price_history_price', 'ml_price_history', ['price'])
    op.create_index('ix_ml_price_history_rooms', 'ml_price_history', ['rooms'])
    op.create_index('ix_ml_price_history_area', 'ml_price_history', ['area'])
    op.create_index('ix_ml_price_history_district', 'ml_price_history', ['district'])
    op.create_index('ix_ml_price_history_floor', 'ml_price_history', ['floor'])
    op.create_index('ix_ml_price_history_source', 'ml_price_history', ['source'])
    op.create_index('ix_ml_price_history_property_type', 'ml_price_history', ['property_type'])
    op.create_index('ix_ml_price_history_is_verified', 'ml_price_history', ['is_verified'])
    op.create_index('ix_ml_price_history_is_active', 'ml_price_history', ['is_active'])
    op.create_index('ix_ml_price_history_price_rooms', 'ml_price_history', ['price', 'rooms'])
    op.create_index('ix_ml_price_history_area_price', 'ml_price_history', ['area', 'price'])
    op.create_index('ix_ml_price_history_source_recorded', 'ml_price_history', ['source', 'recorded_at'])
    op.create_index('ix_ml_price_history_verified_recorded', 'ml_price_history', ['is_verified', 'recorded_at'])
    op.create_index('ix_ml_price_history_floor_recorded', 'ml_price_history', ['floor', 'recorded_at'])
    op.create_index('ix_ml_price_history_city_district_recorded', 'ml_price_history', ['city', 'district', 'recorded_at'])
    op.create_index('ix_ml_price_history_price_per_sqm_calc', 'ml_price_history', ['price', 'area'])


def downgrade() -> None:
    # Downgrade ml_price_history table
    op.drop_index('ix_ml_price_history_price_per_sqm_calc', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_city_district_recorded', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_floor_recorded', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_verified_recorded', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_source_recorded', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_area_price', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_price_rooms', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_is_active', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_is_verified', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_property_type', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_source', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_floor', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_district', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_area', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_rooms', table_name='ml_price_history')
    op.drop_index('ix_ml_price_history_price', table_name='ml_price_history')
    
    # Downgrade property_alerts table
    op.drop_index('ix_property_alerts_area_range', table_name='property_alerts')
    op.drop_index('ix_property_alerts_price_range', table_name='property_alerts')
    op.drop_index('ix_property_alerts_last_notified', table_name='property_alerts')
    op.drop_index('ix_property_alerts_created_at', table_name='property_alerts')
    op.drop_index('ix_property_alerts_max_area', table_name='property_alerts')
    op.drop_index('ix_property_alerts_min_area', table_name='property_alerts')
    op.drop_index('ix_property_alerts_rooms', table_name='property_alerts')
    op.drop_index('ix_property_alerts_min_price', table_name='property_alerts')
    op.drop_index('ix_property_alerts_max_price', table_name='property_alerts')
    
    # Downgrade search_queries table
    op.drop_index('ix_search_queries_price_range', table_name='search_queries')
    op.drop_index('ix_search_queries_city_property_type', table_name='search_queries')
    op.drop_index('ix_search_queries_searched_at', table_name='search_queries')
    op.drop_index('ix_search_queries_max_area', table_name='search_queries')
    op.drop_index('ix_search_queries_min_area', table_name='search_queries')
    op.drop_index('ix_search_queries_rooms', table_name='search_queries')
    op.drop_index('ix_search_queries_min_price', table_name='search_queries')
    op.drop_index('ix_search_queries_max_price', table_name='search_queries')
    op.drop_index('ix_search_queries_property_type', table_name='search_queries')
    
    # Downgrade property_views table
    op.drop_index('ix_property_views_viewed_at', table_name='property_views')
    
    # Downgrade property_price_history table
    op.drop_index('ix_property_price_history_price_change', table_name='property_price_history')
    op.drop_index('ix_property_price_history_changed_at', table_name='property_price_history')
    
    # Downgrade properties table
    op.drop_index('ix_properties_floor_total_floors', table_name='properties')
    op.drop_index('ix_properties_source_first_seen', table_name='properties')
    op.drop_index('ix_properties_area_price_per_sqm', table_name='properties')
    op.drop_index('ix_properties_verified_active', table_name='properties')
    op.drop_index('ix_properties_city_district', table_name='properties')
    op.drop_index('ix_properties_rooms_price', table_name='properties')
    op.drop_index('ix_properties_last_updated', table_name='properties')
    op.drop_index('ix_properties_first_seen', table_name='properties')
    op.drop_index('ix_properties_is_verified', table_name='properties')
    op.drop_index('ix_properties_floor', table_name='properties')
    op.drop_index('ix_properties_area', table_name='properties')
    op.drop_index('ix_properties_rooms', table_name='properties')
    op.drop_index('ix_properties_price_per_sqm', table_name='properties')