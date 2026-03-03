"""Make position_snapshots.debate_id nullable

Revision ID: 001_nullable_debate_id
Revises: None
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = "001_nullable_debate_id"
down_revision = "000_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "position_snapshots",
        "debate_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "position_snapshots",
        "debate_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
