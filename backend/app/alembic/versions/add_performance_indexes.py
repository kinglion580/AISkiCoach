"""Add performance indexes for user sessions

Revision ID: perf_idx_001
Revises: 1a31ce608336
Create Date: 2025-01-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'perf_idx_001'
down_revision = '1a31ce608336'
branch_labels = None
depends_on = None


def upgrade():
    """Add composite index for get_active_sessions query optimization"""
    # Create partial index for active sessions query
    # This optimizes: SELECT * FROM user_sessions WHERE user_id = ? AND is_active = true AND expires_at > ?
    op.create_index(
        'ix_user_sessions_user_active_expires',
        'user_sessions',
        ['user_id', 'is_active', 'expires_at'],
        unique=False,
        postgresql_where=sa.text('is_active = true')
    )


def downgrade():
    """Remove performance indexes"""
    op.drop_index(
        'ix_user_sessions_user_active_expires',
        table_name='user_sessions',
        postgresql_where=sa.text('is_active = true')
    )
