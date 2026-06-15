"""add model_configs tables

Revision ID: a1b2c3d4e5f6
Revises: 8c32a12328f4
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '8c32a12328f4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'model_configs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('model_name', sa.String(200), nullable=False),
        sa.Column('api_key', sa.String(500), nullable=False),
        sa.Column('config_type', sa.String(50), server_default='llm'),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1')),
        sa.Column('is_current', sa.Boolean(), server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_model_configs_id', 'model_configs', ['id'])

    op.create_table(
        'model_config_history',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('config_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('model_name', sa.String(200), nullable=False),
        sa.Column('api_key', sa.String(500), nullable=False),
        sa.Column('config_type', sa.String(50), server_default='llm'),
        sa.Column('changed_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_model_config_history_id', 'model_config_history', ['id'])
    op.create_index('ix_model_config_history_config_id', 'model_config_history', ['config_id'])


def downgrade():
    op.drop_index('ix_model_config_history_config_id')
    op.drop_index('ix_model_config_history_id')
    op.drop_table('model_config_history')
    op.drop_index('ix_model_configs_id')
    op.drop_table('model_configs')
