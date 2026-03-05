from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from uuid_extensions import uuid7

from app.models.base import Base


class OpenDebateStance(Base):
    __tablename__ = "open_debate_stances"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    debate_id: Mapped[UUID] = mapped_column(ForeignKey("debates.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    position_label: Mapped[str] = mapped_column(String(50), default="Nuanced")
    references: Mapped[list] = mapped_column(JSONB, default=list)
    ranking_score: Mapped[int] = mapped_column(default=0)
    penalty_applied: Mapped[bool] = mapped_column(default=False)
    final_rank: Mapped[Optional[int]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("debate_id", "agent_id"),)


class StanceRanking(Base):
    __tablename__ = "stance_rankings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    debate_id: Mapped[UUID] = mapped_column(ForeignKey("debates.id"), index=True)
    voter_agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    ranked_stance_ids: Mapped[list] = mapped_column(JSONB)
    ranking_reasons: Mapped[dict] = mapped_column(JSONB, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (UniqueConstraint("debate_id", "voter_agent_id"),)
