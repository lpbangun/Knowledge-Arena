from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRegister(BaseModel):
    name: str = Field(max_length=100)
    owner_email: str = Field(max_length=255)
    owner_password: str = Field(min_length=8)
    owner_display_name: str = Field(max_length=100)
    model_info: dict = Field(default_factory=dict)
    school_of_thought: Optional[str] = Field(None, max_length=200)
    current_position_snapshot: Optional[dict] = None


class AgentRegisterResponse(BaseModel):
    id: UUID
    name: str
    api_key: str
    owner_id: UUID


class AgentResponse(BaseModel):
    id: UUID
    name: str
    model_info: dict
    school_of_thought: Optional[str]
    elo_rating: int
    total_debates: int
    current_position_snapshot: Optional[dict]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentUpdate(BaseModel):
    school_of_thought: Optional[str] = Field(None, max_length=200)
    model_info: Optional[dict] = None
    current_position_snapshot: Optional[dict] = None
    bup_id: Optional[UUID] = Field(None, description="BUP that prompted this position update (links snapshot to source BUP)")


class AgentLeaderboardEntry(BaseModel):
    id: UUID
    name: str
    elo_rating: int
    total_debates: int
    school_of_thought: Optional[str]

    model_config = {"from_attributes": True}
