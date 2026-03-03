"""Add updated_at to debate_participants and turns

Revision ID: 002_add_updated_at
Revises: 001_nullable_debate_id
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "002_add_updated_at"
down_revision = "001_nullable_debate_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "debate_participants",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.add_column(
        "turns",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_column("turns", "updated_at")
    op.drop_column("debate_participants", "updated_at")
