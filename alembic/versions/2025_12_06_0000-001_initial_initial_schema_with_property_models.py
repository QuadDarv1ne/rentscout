"""Initial schema with property models

Revision ID: 001_initial
Revises: 
Create Date: 2025-12-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create properties table
    op.create_table(
        'properties',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.String(length=5000), nullable=True),
        sa.Column('link', sa.String(length=1000), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('price_per_sqm', sa.Float(), nullable=True),
        sa.Column('rooms', sa.Integer(), nullable=True),
        sa.Column('area', sa.Float(), nullable=True),
        sa.Column('floor', sa.Integer(), nullable=True),
        sa.Column('total_floors', sa.Integer(), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('location', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('photos', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('features', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('contact_name', sa.String(length=200), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=True),
        sa.Column('first_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'external_id', name='uix_source_external_id')
    )
    
    # Create indexes
    op.create_index('ix_properties_id', 'properties', ['id'])
    op.create_index('ix_properties_source', 'properties', ['source'])
    op.create_index('ix_properties_price', 'properties', ['price'])
    op.create_index('ix_properties_city', 'properties', ['city'])
    op.create_index('ix_properties_is_active', 'properties', ['is_active'])
    op.create_index('ix_city_price', 'properties', ['city', 'price'])
    op.create_index('ix_source_city', 'properties', ['source', 'city'])
    op.create_index('ix_active_price', 'properties', ['is_active', 'price'])
    op.create_index('ix_rooms_area', 'properties', ['rooms', 'area'])
    
    # Create property_price_history table
    op.create_table(
        'property_price_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=False),
        sa.Column('old_price', sa.Float(), nullable=True),
        sa.Column('new_price', sa.Float(), nullable=False),
        sa.Column('price_change', sa.Float(), nullable=True),
        sa.Column('price_change_percent', sa.Float(), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_property_price_history_id', 'property_price_history', ['id'])
    op.create_index('ix_property_price_history_property_id', 'property_price_history', ['property_id'])
    op.create_index('ix_property_changed', 'property_price_history', ['property_id', 'changed_at'])
    
    # Create property_views table
    op.create_table(
        'property_views',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('referer', sa.String(length=1000), nullable=True),
        sa.Column('viewed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_property_views_id', 'property_views', ['id'])
    op.create_index('ix_property_views_property_id', 'property_views', ['property_id'])
    op.create_index('ix_property_viewed', 'property_views', ['property_id', 'viewed_at'])
    op.create_index('ix_ip_viewed', 'property_views', ['ip_address', 'viewed_at'])
    
    # Create search_queries table
    op.create_table(
        'search_queries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('property_type', sa.String(length=50), nullable=True),
        sa.Column('min_price', sa.Float(), nullable=True),
        sa.Column('max_price', sa.Float(), nullable=True),
        sa.Column('min_rooms', sa.Integer(), nullable=True),
        sa.Column('max_rooms', sa.Integer(), nullable=True),
        sa.Column('min_area', sa.Float(), nullable=True),
        sa.Column('max_area', sa.Float(), nullable=True),
        sa.Column('query_params', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('results_count', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('searched_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_search_queries_id', 'search_queries', ['id'])
    op.create_index('ix_search_queries_city', 'search_queries', ['city'])
    op.create_index('ix_city_searched', 'search_queries', ['city', 'searched_at'])
    op.create_index('ix_ip_searched', 'search_queries', ['ip_address', 'searched_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('search_queries')
    op.drop_table('property_views')
    op.drop_table('property_price_history')
    op.drop_table('properties')
