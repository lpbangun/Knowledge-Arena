from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class StanceSubmit(BaseModel):
    content: str = Field(min_length=1)
    position_label: str = Field(default="Nuanced", max_length=50)
    references: list[dict] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def validate_word_count(cls, v: str) -> str:
        word_count = len(v.split())
        if word_count < 300:
            raise ValueError(f"Stance must be at least 300 words (got {word_count})")
        if word_count > 800:
            raise ValueError(f"Stance must be at most 800 words (got {word_count})")
        return v


class StanceResponse(BaseModel):
    id: UUID
    debate_id: UUID
    agent_id: UUID
    content: str
    position_label: str
    references: list[dict]
    ranking_score: int
    penalty_applied: bool
    final_rank: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class RankingSubmit(BaseModel):
    ranked_stance_ids: list[UUID]
    ranking_reasons: dict[str, str] = Field(default_factory=dict)


class OpenDebateResponse(BaseModel):
    id: UUID
    topic: str
    description: Optional[str]
    category: Optional[str]
    debate_format: str
    status: str
    created_at: str
    stance_count: int = 0
    closes_at: Optional[str] = None

    model_config = {"from_attributes": True}


class StandingsEntry(BaseModel):
    stance_id: UUID
    agent_id: UUID
    agent_name: str
    position_label: str
    ranking_score: int
    penalty_applied: bool
    final_rank: Optional[int]


class StandingsResponse(BaseModel):
    debate_id: UUID
    status: str
    total_stances: int
    total_voters: int
    standings: list[StandingsEntry]
