"""Add webhook_url column to agents table

Revision ID: 004
Revises: 003
Create Date: 2026-03-08
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agents", sa.Column("webhook_url", sa.String(2000), nullable=True))


def downgrade():
    op.drop_column("agents", "webhook_url")
