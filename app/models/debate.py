from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from uuid_extensions import uuid7

from app.models.base import Base
from app.models.enums import (
    CitationChallengeStatus,
    DebateStatus,
    ParticipantRole,
    TurnValidationStatus,
    VoterType,
)


class Debate(Base):
    __tablename__ = "debates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    topic: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("agents.id"))
    source_thesis_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("theses.id"))
    status: Mapped[DebateStatus] = mapped_column(default=DebateStatus.PHASE_0)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    phase_0_structure: Mapped[Optional[dict]] = mapped_column(JSONB)
    max_rounds: Mapped[int] = mapped_column(default=10)
    current_round: Mapped[int] = mapped_column(default=0)
    convergence_signals: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class DebateParticipant(Base):
    __tablename__ = "debate_participants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    debate_id: Mapped[UUID] = mapped_column(ForeignKey("debates.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    role: Mapped[ParticipantRole] = mapped_column()
    school_of_thought: Mapped[Optional[str]] = mapped_column(String(200))
    hard_core: Mapped[Optional[str]] = mapped_column(Text)
    auxiliary_hypotheses: Mapped[Optional[list]] = mapped_column(JSONB)
    citation_challenges_remaining: Mapped[int] = mapped_column(default=3)
    joined_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("debate_id", "agent_id"),)


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    debate_id: Mapped[UUID] = mapped_column(ForeignKey("debates.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    round_number: Mapped[int] = mapped_column()
    turn_type: Mapped[str] = mapped_column(String(20), default="argument")
    content: Mapped[str] = mapped_column(Text)
    toulmin_tags: Mapped[list] = mapped_column(JSONB, default=list)
    falsification_target: Mapped[Optional[dict]] = mapped_column(JSONB)
    citation_references: Mapped[list] = mapped_column(JSONB, default=list)
    validation_status: Mapped[TurnValidationStatus] = mapped_column(default=TurnValidationStatus.PENDING)
    validation_feedback: Mapped[Optional[str]] = mapped_column(Text)
    arbiter_quality_score: Mapped[Optional[float]] = mapped_column()
    audience_avg_score: Mapped[Optional[float]] = mapped_column()
    human_avg_score: Mapped[Optional[float]] = mapped_column()
    agent_avg_score: Mapped[Optional[float]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class CitationChallenge(Base):
    __tablename__ = "citation_challenges"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    debate_id: Mapped[UUID] = mapped_column(ForeignKey("debates.id"), index=True)
    challenger_id: Mapped[UUID] = mapped_column()
    challenger_type: Mapped[VoterType] = mapped_column()
    target_turn_id: Mapped[UUID] = mapped_column(ForeignKey("turns.id"))
    target_citation_index: Mapped[int] = mapped_column()
    status: Mapped[CitationChallengeStatus] = mapped_column(default=CitationChallengeStatus.PENDING)
    response_evidence: Mapped[Optional[dict]] = mapped_column(JSONB)
    arbiter_ruling: Mapped[Optional[str]] = mapped_column(Text)
    elo_impact: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
