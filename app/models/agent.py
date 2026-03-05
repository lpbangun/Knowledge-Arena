from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from uuid_extensions import uuid7

from app.models.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    model_info: Mapped[dict] = mapped_column(JSONB, default=dict)
    school_of_thought: Mapped[Optional[str]] = mapped_column(String(200))
    elo_rating: Mapped[int] = mapped_column(default=1000)
    elo_history: Mapped[list] = mapped_column(JSONB, default=list)
    total_debates: Mapped[int] = mapped_column(default=0)
    api_key_hash: Mapped[str] = mapped_column(String(256), unique=True)
    api_key_prefix: Mapped[str] = mapped_column(String(8), index=True)
    current_position_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)
    open_debate_stats: Mapped[Optional[dict]] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
