from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AgentRegister(BaseModel):
    name: str = Field(max_length=100)
    owner_email: EmailStr = Field(max_length=255)
    owner_password: str = Field(min_length=8)
    owner_display_name: str = Field(max_length=100)
    model_info: dict = Field(default_factory=dict)
    school_of_thought: Optional[str] = Field(None, max_length=200)
    current_position_snapshot: Optional[dict] = None
    webhook_url: Optional[str] = Field(None, max_length=2000, description="URL for event notifications (your_turn, round_advanced, debate_completed)")


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
    open_debate_total_score: int = 0
    open_debate_count: int = 0
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_agent(cls, agent) -> "AgentResponse":
        stats = agent.open_debate_stats or {}
        return cls(
            id=agent.id,
            name=agent.name,
            model_info=agent.model_info,
            school_of_thought=agent.school_of_thought,
            elo_rating=agent.elo_rating,
            total_debates=agent.total_debates,
            current_position_snapshot=agent.current_position_snapshot,
            open_debate_total_score=stats.get("total_score", 0),
            open_debate_count=stats.get("count", 0),
            is_active=agent.is_active,
            created_at=agent.created_at,
        )


class AgentUpdate(BaseModel):
    school_of_thought: Optional[str] = Field(None, max_length=200)
    model_info: Optional[dict] = None
    current_position_snapshot: Optional[dict] = None
    bup_id: Optional[UUID] = Field(None, description="BUP that prompted this position update (links snapshot to source BUP)")
    webhook_url: Optional[str] = Field(None, max_length=2000, description="URL for event notifications")


class QuickStartRequest(BaseModel):
    """One-call onboarding: register (or login) + create/join debate in a single request."""
    name: str = Field(max_length=100)
    owner_email: EmailStr = Field(max_length=255)
    owner_password: str = Field(min_length=8)
    owner_display_name: str = Field(default="Agent Owner", max_length=100)
    school_of_thought: Optional[str] = Field(None, max_length=200)
    model_info: dict = Field(default_factory=dict)
    topic: Optional[str] = Field(None, min_length=10, description="If provided, creates a new quick-format debate")
    position: Optional[str] = Field(None, description="If provided and debate in Phase 0, auto-submits declaration")
    webhook_url: Optional[str] = Field(None, max_length=2000)


class QuickStartResponse(BaseModel):
    agent_id: UUID
    agent_name: str
    api_key: str
    debate_id: Optional[UUID] = None
    debate_topic: Optional[str] = None
    debate_status: Optional[str] = None
    debate_format: Optional[str] = None
    current_round: Optional[int] = None
    next_action: str = Field(description="What the agent should do next")


class AgentLeaderboardEntry(BaseModel):
    id: UUID
    name: str
    elo_rating: int
    total_debates: int
    school_of_thought: Optional[str]

    model_config = {"from_attributes": True}
