"""Add ML price history table

Revision ID: 82868aac266e
Revises: 001_initial
Create Date: 2025-12-08 19:19:40.486777

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '82868aac266e'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ml_price_history table
    op.create_table(
        'ml_price_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('rooms', sa.Integer(), nullable=True),
        sa.Column('area', sa.Float(), nullable=True),
        sa.Column('district', sa.String(100), nullable=True),
        sa.Column('floor', sa.Integer(), nullable=True),
        sa.Column('total_floors', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(50), nullable=True),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('property_type', sa.String(50), nullable=False, server_default='apartment'),
        sa.Column('is_verified', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('currency', sa.String(10), nullable=False, server_default='RUB'),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_city_recorded', 'ml_price_history', ['city', 'recorded_at'])
    op.create_index('ix_city_rooms_recorded', 'ml_price_history', ['city', 'rooms', 'recorded_at'])
    op.create_index('ix_city_area_recorded', 'ml_price_history', ['city', 'area', 'recorded_at'])
    op.create_index('ix_district_recorded', 'ml_price_history', ['district', 'recorded_at'])
    op.create_index('ix_recorded_at', 'ml_price_history', ['recorded_at'])
    op.create_index('ix_is_active_recorded', 'ml_price_history', ['is_active', 'recorded_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_is_active_recorded', table_name='ml_price_history')
    op.drop_index('ix_recorded_at', table_name='ml_price_history')
    op.drop_index('ix_district_recorded', table_name='ml_price_history')
    op.drop_index('ix_city_area_recorded', table_name='ml_price_history')
    op.drop_index('ix_city_rooms_recorded', table_name='ml_price_history')
    op.drop_index('ix_city_recorded', table_name='ml_price_history')
    
    # Drop table
    op.drop_table('ml_price_history')
