"""add 2FA indexes for better performance

Revision ID: 2026_03_20_add_2fa_indexes
Revises: 2026_03_20_add_users
Create Date: 2026-03-20

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_03_20_add_2fa_indexes'
down_revision = '2026_03_20_add_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add indexes for 2FA fields
    op.create_index('ix_users_two_factor_enabled', 'users', ['two_factor_enabled'], unique=False)
    op.create_index('ix_users_two_factor_secret', 'users', ['two_factor_secret'], unique=False)
    op.create_index('ix_users_backup_codes', 'users', ['backup_codes'], unique=False)
    
    # Composite index for 2FA login optimization
    op.create_index(
        'ix_users_two_factor_lookup',
        'users',
        ['username', 'two_factor_enabled', 'is_active'],
        unique=False
    )


def downgrade() -> None:
    # Drop composite index
    op.drop_index('ix_users_two_factor_lookup', table_name='users')
    
    # Drop individual indexes
    op.drop_index('ix_users_backup_codes', table_name='users')
    op.drop_index('ix_users_two_factor_secret', table_name='users')
    op.drop_index('ix_users_two_factor_enabled', table_name='users')
