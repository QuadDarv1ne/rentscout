"""add users table and owner relationship

Revision ID: 2026_03_20_add_users
Revises: 2026_02_21_optimized_indexes
Create Date: 2026-03-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Enum as SQLEnum


# revision identifiers, used by Alembic.
revision = '2026_03_20_add_users'
down_revision = '2026_02_21_optimized_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', SQLEnum('user', 'admin', 'moderator', name='userrole'), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for users table
    op.create_index('ix_users_id', 'users', ['id'], unique=False)
    op.create_index('ix_users_username', 'users', ['username'], unique=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=False)
    op.create_index('ix_users_username_active', 'users', ['username', 'is_active'], unique=False)
    op.create_index('ix_users_email_active', 'users', ['email', 'is_active'], unique=False)
    op.create_index('ix_users_role', 'users', ['role'], unique=False)
    
    # Add owner_id column to properties table
    op.add_column('properties', sa.Column('owner_id', sa.Integer(), nullable=True))
    
    # Create index for owner_id
    op.create_index('ix_properties_owner_id', 'properties', ['owner_id'], unique=False)
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_properties_owner_id_users',
        'properties', 'users',
        ['owner_id'], ['id']
    )


def downgrade() -> None:
    # Drop foreign key
    op.drop_constraint('fk_properties_owner_id_users', 'properties', type_='foreignkey')
    
    # Drop owner_id column
    op.drop_index('ix_properties_owner_id', table_name='properties')
    op.drop_column('properties', 'owner_id')
    
    # Drop users table indexes
    op.drop_index('ix_users_role', table_name='users')
    op.drop_index('ix_users_email_active', table_name='users')
    op.drop_index('ix_users_username_active', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_id', table_name='users')
    
    # Drop users table
    op.drop_table('users')
