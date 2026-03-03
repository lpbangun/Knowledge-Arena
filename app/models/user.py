from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column
from uuid_extensions import uuid7

from app.models.base import Base
from app.models.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[Optional[str]] = mapped_column(String(256))
    auth_provider: Mapped[str] = mapped_column(String(50), default="email")
    role: Mapped[UserRole] = mapped_column(default=UserRole.OBSERVER)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
