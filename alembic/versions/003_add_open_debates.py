"""Add open debates tables and columns

Revision ID: 003
Revises: 002
Create Date: 2026-03-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    # Add debate_format column to debates
    op.add_column("debates", sa.Column("debate_format", sa.String(20), server_default="lakatos", nullable=False))

    # Add open_debate_stats JSONB column to agents
    op.add_column("agents", sa.Column("open_debate_stats", postgresql.JSONB(), nullable=True))

    # Create open_debate_stances table
    op.create_table(
        "open_debate_stances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=False, index=True),
        sa.Column("agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("position_label", sa.String(50), server_default="Nuanced", nullable=False),
        sa.Column("references", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("ranking_score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("penalty_applied", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("final_rank", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("debate_id", "agent_id"),
    )

    # Create stance_rankings table
    op.create_table(
        "stance_rankings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("debate_id", sa.Uuid(), sa.ForeignKey("debates.id"), nullable=False, index=True),
        sa.Column("voter_agent_id", sa.Uuid(), sa.ForeignKey("agents.id"), nullable=False, index=True),
        sa.Column("ranked_stance_ids", postgresql.JSONB(), nullable=False),
        sa.Column("ranking_reasons", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("submitted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("debate_id", "voter_agent_id"),
    )


def downgrade():
    op.drop_table("stance_rankings")
    op.drop_table("open_debate_stances")
    op.drop_column("agents", "open_debate_stats")
    op.drop_column("debates", "debate_format")
