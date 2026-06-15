"""add converted_text to documents

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('documents', sa.Column('converted_text', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('documents', 'converted_text')
