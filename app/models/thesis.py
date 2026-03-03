from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from uuid_extensions import uuid7

from app.models.base import Base
from app.models.enums import ThesisStatus


class Thesis(Base):
    __tablename__ = "theses"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)
    claim: Mapped[str] = mapped_column(Text)
    school_of_thought: Mapped[Optional[str]] = mapped_column(String(200))
    evidence_summary: Mapped[Optional[str]] = mapped_column(Text)
    challenge_type: Mapped[Optional[str]] = mapped_column(String(100))
    toulmin_tags: Mapped[Optional[list]] = mapped_column(JSONB)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    is_gap_filling: Mapped[bool] = mapped_column(default=False)
    gap_reference: Mapped[Optional[UUID]] = mapped_column(ForeignKey("graph_nodes.id"))
    status: Mapped[ThesisStatus] = mapped_column(default=ThesisStatus.OPEN)
    view_count: Mapped[int] = mapped_column(default=0)
    challenger_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
