from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from uuid_extensions import uuid7

from app.models.base import Base
from app.models.enums import VoteType, VoterType


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    vote_type: Mapped[VoteType] = mapped_column()
    target_id: Mapped[UUID] = mapped_column(index=True)
    voter_type: Mapped[VoterType] = mapped_column()
    voter_id: Mapped[UUID] = mapped_column()
    score: Mapped[Optional[int]] = mapped_column()
    outcome_choice: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (UniqueConstraint("target_id", "voter_id", "vote_type"),)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    debate_id: Mapped[UUID] = mapped_column(ForeignKey("debates.id"), index=True)
    target_turn_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("turns.id"))
    author_type: Mapped[VoterType] = mapped_column()
    author_id: Mapped[UUID] = mapped_column()
    parent_comment_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("comments.id"))
    content: Mapped[str] = mapped_column(Text)
    upvote_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AmicusBrief(Base):
    __tablename__ = "amicus_briefs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    debate_id: Mapped[UUID] = mapped_column(ForeignKey("debates.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"))
    content: Mapped[str] = mapped_column(Text)
    toulmin_tags: Mapped[Optional[list]] = mapped_column(JSONB)
    relevance_score: Mapped[Optional[float]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
