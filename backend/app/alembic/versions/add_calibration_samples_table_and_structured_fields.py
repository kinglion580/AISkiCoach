"""add calibration samples table and structured fields

Revision ID: f1a2b3c4d5e6
Revises: cc9d2e67ab33
Create Date: 2025-01-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'cc9d2e67ab33'
branch_labels = None
depends_on = None


def upgrade():
    # 添加新的结构化字段到 device_calibrations 表
    op.add_column('device_calibrations', 
        sa.Column('rotation_matrix', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('installation_angles', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('purity', sa.Numeric(precision=10, scale=6), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('static_window_start', sa.Integer(), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('static_window_end', sa.Integer(), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('rotation_window_start', sa.Integer(), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('rotation_window_end', sa.Integer(), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('static_window_size', sa.Integer(), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('rotation_window_size', sa.Integer(), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('rotation_purity_threshold', sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('total_samples', sa.Integer(), nullable=True))
    op.add_column('device_calibrations',
        sa.Column('sample_rate', sa.Numeric(precision=10, scale=2), nullable=True))
    
    # 创建 device_calibration_samples 表
    op.create_table('device_calibration_samples',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('calibration_id', sa.Uuid(), nullable=False),
        sa.Column('sample_index', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('acc_x', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('acc_y', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('acc_z', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('gyro_x', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('gyro_y', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('gyro_z', sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['calibration_id'], ['device_calibrations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_device_calibration_samples_calibration_id'), 
        'device_calibration_samples', ['calibration_id'], unique=False)
    op.create_index(op.f('ix_device_calibration_samples_sample_index'), 
        'device_calibration_samples', ['sample_index'], unique=False)
    op.create_index(op.f('ix_device_calibration_samples_timestamp'), 
        'device_calibration_samples', ['timestamp'], unique=False)


def downgrade():
    # 删除 device_calibration_samples 表
    op.drop_index(op.f('ix_device_calibration_samples_timestamp'), table_name='device_calibration_samples')
    op.drop_index(op.f('ix_device_calibration_samples_sample_index'), table_name='device_calibration_samples')
    op.drop_index(op.f('ix_device_calibration_samples_calibration_id'), table_name='device_calibration_samples')
    op.drop_table('device_calibration_samples')
    
    # 删除 device_calibrations 表的新字段
    op.drop_column('device_calibrations', 'sample_rate')
    op.drop_column('device_calibrations', 'total_samples')
    op.drop_column('device_calibrations', 'rotation_purity_threshold')
    op.drop_column('device_calibrations', 'rotation_window_size')
    op.drop_column('device_calibrations', 'static_window_size')
    op.drop_column('device_calibrations', 'rotation_window_end')
    op.drop_column('device_calibrations', 'rotation_window_start')
    op.drop_column('device_calibrations', 'static_window_end')
    op.drop_column('device_calibrations', 'static_window_start')
    op.drop_column('device_calibrations', 'purity')
    op.drop_column('device_calibrations', 'installation_angles')
    op.drop_column('device_calibrations', 'rotation_matrix')

