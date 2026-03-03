from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from uuid_extensions import uuid7

from app.models.base import Base
from app.models.enums import SnapshotType


class DebateEvaluation(Base):
    __tablename__ = "debate_evaluations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    debate_id: Mapped[UUID] = mapped_column(ForeignKey("debates.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"))
    argument_quality: Mapped[float] = mapped_column()
    falsification_effectiveness: Mapped[float] = mapped_column()
    protective_belt_integrity: Mapped[float] = mapped_column()
    novel_contribution: Mapped[float] = mapped_column()
    structural_compliance: Mapped[float] = mapped_column()
    composite_score: Mapped[float] = mapped_column()
    elo_before: Mapped[int] = mapped_column()
    elo_after: Mapped[int] = mapped_column()
    narrative_feedback: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SynthesisDocument(Base):
    __tablename__ = "synthesis_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    debate_id: Mapped[UUID] = mapped_column(ForeignKey("debates.id"), unique=True)
    agreements: Mapped[str] = mapped_column(Text)
    disagreements: Mapped[str] = mapped_column(Text)
    novel_positions: Mapped[str] = mapped_column(Text)
    open_questions: Mapped[str] = mapped_column(Text)
    graph_nodes_created: Mapped[list] = mapped_column(JSONB, default=list)
    graph_edges_created: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BeliefUpdatePacket(Base):
    __tablename__ = "belief_update_packets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    debate_id: Mapped[UUID] = mapped_column(ForeignKey("debates.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    concessions_made: Mapped[list] = mapped_column(JSONB, default=list)
    concessions_resisted: Mapped[list] = mapped_column(JSONB, default=list)
    new_evidence: Mapped[list] = mapped_column(JSONB, default=list)
    strongest_counterarguments: Mapped[list] = mapped_column(JSONB, default=list)
    synthesis_insights: Mapped[list] = mapped_column(JSONB, default=list)
    recommended_updates: Mapped[list] = mapped_column(JSONB, default=list)
    falsification_outcomes: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    debate_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("debates.id"), nullable=True)
    bup_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("belief_update_packets.id"), nullable=True)
    snapshot_type: Mapped[SnapshotType] = mapped_column()
    hard_core: Mapped[str] = mapped_column(Text)
    auxiliary_hypotheses: Mapped[list] = mapped_column(JSONB)
    qualifier_count: Mapped[int] = mapped_column(default=0)
    evidence_references: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
