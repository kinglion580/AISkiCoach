"""Merge barometer_data and json_fields branches

Revision ID: a06a8c9c73df
Revises: 981f2857c0f7, a1b2c3d4e5f6
Create Date: 2025-11-08 12:12:47.204098

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a06a8c9c73df'
down_revision = ('981f2857c0f7', 'a1b2c3d4e5f6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
