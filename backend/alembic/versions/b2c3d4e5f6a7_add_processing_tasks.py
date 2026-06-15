"""add processing_tasks table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'processing_tasks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('document_id', sa.Integer(), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('knowledge_base_id', sa.Integer(), sa.ForeignKey('knowledge_bases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('current_step', sa.String(50), nullable=True),
        sa.Column('events', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_processing_tasks_id', 'processing_tasks', ['id'])
    op.create_index('ix_processing_tasks_document_id', 'processing_tasks', ['document_id'])
    op.create_index('ix_processing_tasks_status', 'processing_tasks', ['status'])


def downgrade():
    op.drop_index('ix_processing_tasks_status')
    op.drop_index('ix_processing_tasks_document_id')
    op.drop_index('ix_processing_tasks_id')
    op.drop_table('processing_tasks')
