from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from uuid_extensions import uuid7

from app.models.base import Base
from app.models.enums import GraphEdgeType, GraphNodeType, VerificationStatus


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    node_type: Mapped[GraphNodeType] = mapped_column(index=True)
    content: Mapped[str] = mapped_column(Text)
    source_debate_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("debates.id"))
    source_agent_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("agents.id"))
    source_turn_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("turns.id"))
    toulmin_category: Mapped[Optional[str]] = mapped_column(String(20))
    verification_status: Mapped[VerificationStatus] = mapped_column(default=VerificationStatus.UNVERIFIED)
    quality_score: Mapped[Optional[float]] = mapped_column()
    challenge_count: Mapped[int] = mapped_column(default=0)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    source_node_id: Mapped[UUID] = mapped_column(ForeignKey("graph_nodes.id"), index=True)
    target_node_id: Mapped[UUID] = mapped_column(ForeignKey("graph_nodes.id"), index=True)
    edge_type: Mapped[GraphEdgeType] = mapped_column()
    source_debate_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("debates.id"))
    source_agent_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("agents.id"))
    strength: Mapped[float] = mapped_column(default=0.5)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
