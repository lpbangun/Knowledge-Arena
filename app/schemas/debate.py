from datetime import datetime
from typing import Optional
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.models.enums import DebateStatus, ParticipantRole, TurnValidationStatus


TOULMIN_TAG_TYPES = Literal["claim", "data", "warrant", "backing", "qualifier", "rebuttal"]


class ToulminTag(BaseModel):
    """A single Toulmin argument tag with character-offset span."""
    type: TOULMIN_TAG_TYPES
    start: int = Field(ge=0, description="Start character offset into turn content")
    end: int = Field(gt=0, description="End character offset into turn content")
    label: str = Field(min_length=1, max_length=500, description="Human-readable label for this tag")

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: int, info) -> int:
        start = info.data.get("start")
        if start is not None and v <= start:
            raise ValueError("end must be greater than start")
        return v


class CitationReference(BaseModel):
    """A citation reference attached to a turn."""
    source: str = Field(min_length=1, max_length=500, description="Source name or title")
    url: Optional[str] = Field(None, max_length=2000, description="URL to the source")
    excerpt: Optional[str] = Field(None, max_length=2000, description="Relevant excerpt from the source")


ALLOWED_CONFIG_KEYS = {
    "allow_audience_voting", "allow_amicus_briefs", "require_citations",
    "custom_rules", "citation_challenges_per_debater",
    "citation_challenges_per_audience", "turn_deadline_seconds", "max_agents",
}


class DebateCreate(BaseModel):
    topic: str = Field(min_length=10)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=100)
    config: dict = Field(default_factory=dict)
    max_rounds: int = Field(default=10, ge=2, le=50)

    @field_validator("config")
    @classmethod
    def validate_config_keys(cls, v: dict) -> dict:
        unknown = set(v.keys()) - ALLOWED_CONFIG_KEYS
        if unknown:
            raise ValueError(f"Unknown config keys: {', '.join(unknown)}")
        return v


class DebateResponse(BaseModel):
    id: UUID
    topic: str
    description: Optional[str]
    category: Optional[str]
    created_by: UUID
    source_thesis_id: Optional[UUID]
    status: DebateStatus
    config: dict
    phase_0_structure: Optional[dict]
    max_rounds: int
    current_round: int
    convergence_signals: Optional[dict]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class DebateJoin(BaseModel):
    role: ParticipantRole = ParticipantRole.DEBATER


class ParticipantResponse(BaseModel):
    id: UUID
    debate_id: UUID
    agent_id: UUID
    role: ParticipantRole
    school_of_thought: Optional[str]
    joined_at: datetime

    model_config = {"from_attributes": True}


class TurnSubmit(BaseModel):
    content: str = Field(max_length=settings.MAX_TURN_CONTENT_CHARS)
    turn_type: str = Field(default="argument", pattern="^(phase_0_declaration|phase_0_negotiation|argument|resubmission)$")
    toulmin_tags: list[ToulminTag] = Field(default_factory=list, max_length=settings.MAX_TOULMIN_TAGS)
    falsification_target: Optional[dict] = None
    citation_references: list[CitationReference] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Content cannot be empty")
        return v

    @field_validator("toulmin_tags")
    @classmethod
    def validate_minimum_tags(cls, v: list[ToulminTag], info) -> list[ToulminTag]:
        turn_type = info.data.get("turn_type", "argument")
        if turn_type in ("argument", "resubmission") and v:
            tag_types = {t.type for t in v}
            missing = {"claim", "data", "warrant"} - tag_types
            if missing:
                raise ValueError(f"Argument turns require at least 1 claim, 1 data, and 1 warrant tag. Missing: {', '.join(missing)}")
        return v


class ControlPlane(BaseModel):
    """Agent-specific debate state signals for autonomous coordination."""
    my_submission_status: str = Field(description="pending | submitted | validated | rejected")
    round_submissions: dict = Field(description="{'total': int, 'submitted': int}")
    turn_deadline_at: Optional[datetime] = None
    action_needed: str = Field(description="submit_turn | wait | debate_complete | resubmit")


class DebateStatusResponse(DebateResponse):
    """Extended debate response with agent-specific control plane."""
    control_plane: Optional[ControlPlane] = None

    model_config = {"from_attributes": True}


class VoteCreate(BaseModel):
    vote_type: str
    target_id: UUID
    score: Optional[int] = Field(None, ge=1, le=5)
    outcome_choice: Optional[str] = None


class CommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    target_turn_id: Optional[UUID] = None
    parent_comment_id: Optional[UUID] = None


class AmicusBriefCreate(BaseModel):
    content: str = Field(max_length=50000)
    toulmin_tags: Optional[list[str]] = None


class CitationChallengeCreate(BaseModel):
    target_turn_id: UUID
    target_citation_index: int = Field(ge=0)


class TurnResponse(BaseModel):
    id: UUID
    debate_id: UUID
    agent_id: UUID
    round_number: int
    turn_type: str
    content: str
    toulmin_tags: list
    falsification_target: Optional[dict]
    citation_references: list
    validation_status: TurnValidationStatus
    validation_feedback: Optional[str]
    arbiter_quality_score: Optional[float]
    audience_avg_score: Optional[float]
    human_avg_score: Optional[float]
    agent_avg_score: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}
