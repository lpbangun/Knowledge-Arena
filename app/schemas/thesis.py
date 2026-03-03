from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ThesisCreate(BaseModel):
    claim: str = Field(min_length=20)
    school_of_thought: Optional[str] = None
    evidence_summary: Optional[str] = None
    challenge_type: Optional[str] = Field(None, max_length=100)
    toulmin_tags: Optional[list[dict]] = None
    category: Optional[str] = Field(None, max_length=100)
    is_gap_filling: bool = False
    gap_reference: Optional[UUID] = None


class ThesisResponse(BaseModel):
    id: UUID
    agent_id: UUID
    claim: str
    school_of_thought: Optional[str]
    evidence_summary: Optional[str]
    challenge_type: Optional[str]
    category: Optional[str]
    is_gap_filling: bool
    gap_reference: Optional[UUID]
    status: str
    view_count: int
    challenger_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ThesisAccept(BaseModel):
    """Accept a thesis challenge — creates a debate."""
    max_rounds: int = Field(default=8, ge=2, le=50)
    config: dict = Field(default_factory=dict)
