"""remove calibration_data column and add failure_reason

Revision ID: c123456789ab
Revises: f1a2b3c4d5e6
Create Date: 2025-11-13 00:15:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "c123456789ab"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("device_calibrations", "calibration_data")
    op.add_column(
        "device_calibrations",
        sa.Column("failure_reason", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("device_calibrations", "failure_reason")
    op.add_column(
        "device_calibrations",
        sa.Column("calibration_data", postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )
