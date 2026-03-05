import json
from datetime import datetime
from typing import Any, Optional, Union
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings
from app.models.enums import DebateStatus, ParticipantRole, TurnValidationStatus


TOULMIN_TAG_TYPES = Literal["claim", "data", "warrant", "backing", "qualifier", "rebuttal"]
VALID_TAG_TYPES = {"claim", "data", "warrant", "backing", "qualifier", "rebuttal"}


class ToulminTag(BaseModel):
    """A single Toulmin argument tag with character-offset span."""
    type: str  # Relaxed from Literal — we coerce in TurnSubmit
    start: int = Field(default=0, ge=0, description="Start character offset into turn content")
    end: int = Field(default=1, gt=0, description="End character offset into turn content")
    label: str = Field(default="", max_length=500, description="Human-readable label for this tag")

    @field_validator("type", mode="before")
    @classmethod
    def coerce_tag_type(cls, v: Any) -> str:
        v = str(v).lower().strip()
        if v in VALID_TAG_TYPES:
            return v
        # Map common agent variants
        mappings = {
            "claims": "claim", "evidence": "data", "proof": "data",
            "reasoning": "warrant", "justification": "warrant",
            "counter": "rebuttal", "counterargument": "rebuttal",
            "caveat": "qualifier", "limitation": "qualifier",
            "support": "backing", "foundation": "backing",
        }
        return mappings.get(v, "claim")


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
    content: Union[str, dict, list] = Field(description="Turn content — string preferred, dicts auto-serialized to JSON")
    turn_type: str = Field(default="argument")
    toulmin_tags: list[Any] = Field(default_factory=list)
    falsification_target: Optional[dict] = None
    citation_references: list[Any] = Field(default_factory=list)

    # Accept common agent field name variants
    # Agents often send "type" or "turn" instead of "turn_type"
    declaration: Optional[Any] = Field(None, exclude=True)
    hard_core: Optional[Any] = Field(None, exclude=True)
    auxiliary_hypotheses: Optional[Any] = Field(None, exclude=True)
    position: Optional[Any] = Field(None, exclude=True)
    argument: Optional[Any] = Field(None, exclude=True)
    citations: Optional[list] = Field(None, exclude=True)
    tags: Optional[list] = Field(None, exclude=True)
    references: Optional[list] = Field(None, exclude=True)

    @field_validator("turn_type", mode="before")
    @classmethod
    def coerce_turn_type(cls, v: Any) -> str:
        v = str(v).lower().strip().replace(" ", "_").replace("-", "_")
        valid = {"phase_0_declaration", "phase_0_negotiation", "argument", "resubmission"}
        if v in valid:
            return v
        # Map common variants
        mappings = {
            "declaration": "phase_0_declaration", "phase0_declaration": "phase_0_declaration",
            "phase0declaration": "phase_0_declaration", "p0_declaration": "phase_0_declaration",
            "negotiation": "phase_0_negotiation", "phase0_negotiation": "phase_0_negotiation",
            "phase0negotiation": "phase_0_negotiation", "p0_negotiation": "phase_0_negotiation",
            "rebuttal": "argument", "response": "argument", "reply": "argument",
            "resubmit": "resubmission",
        }
        return mappings.get(v, "argument")

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        # If agent sent "citations" or "references" instead of "citation_references"
        if "citations" in values and "citation_references" not in values:
            values["citation_references"] = values.pop("citations")
        if "references" in values and "citation_references" not in values:
            refs = values.pop("references")
            # Normalize: if refs are strings, wrap them
            if isinstance(refs, list):
                values["citation_references"] = [
                    r if isinstance(r, dict) else {"source": str(r)}
                    for r in refs
                ]

        # If agent sent "tags" instead of "toulmin_tags"
        if "tags" in values and "toulmin_tags" not in values:
            values["toulmin_tags"] = values.pop("tags")

        # If content is missing but structured fields exist, build content from them
        content = values.get("content")
        if content is None or content == "":
            parts = []
            for field in ("declaration", "hard_core", "position", "argument"):
                val = values.get(field)
                if val:
                    if isinstance(val, dict):
                        parts.append(json.dumps(val, indent=2))
                    elif isinstance(val, str):
                        parts.append(val)
            aux = values.get("auxiliary_hypotheses")
            if aux:
                if isinstance(aux, list):
                    parts.append("Auxiliary hypotheses: " + "; ".join(str(a) for a in aux))
                elif isinstance(aux, str):
                    parts.append("Auxiliary hypotheses: " + aux)
            if parts:
                values["content"] = "\n\n".join(parts)

        # Auto-detect turn_type from field names if not set or defaulted
        if values.get("turn_type") in (None, "", "argument"):
            if values.get("declaration") or values.get("hard_core"):
                values["turn_type"] = "phase_0_declaration"

        return values

    @field_validator("content", mode="before")
    @classmethod
    def coerce_content(cls, v: Any) -> str:
        if isinstance(v, dict):
            return json.dumps(v, indent=2, ensure_ascii=False)
        if isinstance(v, list):
            return json.dumps(v, indent=2, ensure_ascii=False)
        v = str(v)
        if not v.strip():
            raise ValueError("Content cannot be empty")
        return v

    @field_validator("toulmin_tags", mode="before")
    @classmethod
    def coerce_tags(cls, v: Any) -> list:
        if not v:
            return []
        if not isinstance(v, list):
            return []
        result = []
        for tag in v:
            if isinstance(tag, dict):
                # Fix missing start/end — set to span the whole content
                if "start" not in tag:
                    tag["start"] = 0
                if "end" not in tag:
                    tag["end"] = 1  # Will be fixed in model_validator
                if "label" not in tag:
                    tag["label"] = tag.get("type", "tag")
                if "type" not in tag:
                    tag["type"] = "claim"
                result.append(tag)
            elif isinstance(tag, str):
                # String tags — treat as claim labels
                result.append({"type": "claim", "start": 0, "end": 1, "label": tag})
        return result

    @field_validator("citation_references", mode="before")
    @classmethod
    def coerce_citations(cls, v: Any) -> list:
        if not v:
            return []
        if not isinstance(v, list):
            return []
        result = []
        for ref in v:
            if isinstance(ref, str):
                result.append({"source": ref})
            elif isinstance(ref, dict):
                if "source" not in ref:
                    ref["source"] = ref.get("title", ref.get("name", ref.get("url", "Unknown source")))
                result.append(ref)
        return result

    @model_validator(mode="after")
    def fix_tag_offsets(self) -> "TurnSubmit":
        """Fix tag offsets to be within content bounds. Auto-generated tags (end=1) span full content."""
        content_len = len(self.content) if isinstance(self.content, str) else 1
        if content_len == 0:
            content_len = 1
        fixed_tags = []
        for tag in self.toulmin_tags:
            if isinstance(tag, ToulminTag):
                # Auto-generated tags with placeholder end=1 → span full content
                if tag.start == 0 and tag.end == 1 and content_len > 1:
                    tag.end = content_len
                # Clamp to content bounds
                if tag.start >= content_len:
                    tag.start = 0
                if tag.end > content_len:
                    tag.end = content_len
                if tag.end <= tag.start:
                    tag.end = content_len
                fixed_tags.append(tag)
            elif isinstance(tag, dict):
                start = min(tag.get("start", 0), content_len - 1)
                end = tag.get("end", content_len)
                if start == 0 and end == 1 and content_len > 1:
                    end = content_len
                end = min(end, content_len)
                if end <= start:
                    end = content_len
                t = ToulminTag(type=tag.get("type", "claim"), start=start, end=end, label=tag.get("label", ""))
                fixed_tags.append(t)
        self.toulmin_tags = fixed_tags
        return self


class ControlPlane(BaseModel):
    """Agent-specific debate state signals for autonomous coordination."""
    my_submission_status: str = Field(description="pending | submitted | validated | rejected")
    round_submissions: dict = Field(description="{'total': int, 'submitted': int}")
    turn_deadline_at: Optional[datetime] = None
    action_needed: str = Field(description="submit_turn | wait | debate_complete | resubmit")
    action_hint: Optional[str] = Field(None, description="Human-readable instruction for what to do next")


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
