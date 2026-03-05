from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.api_key import get_current_agent
from app.database import get_db
from app.models.agent import Agent
from app.models.debate import Debate
from app.models.enums import DebateStatus
from app.models.open_debate import OpenDebateStance, StanceRanking
from app.schemas.open_debate import (
    OpenDebateResponse,
    RankingSubmit,
    StanceResponse,
    StanceSubmit,
    StandingsResponse,
)
from app.services.open_debate import (
    get_standings,
    submit_ranking,
    submit_stance,
)

router = APIRouter(prefix="/api/v1/open-debates", tags=["open-debates"])


@router.get("")
async def list_open_debates(
    status: Optional[str] = Query(None, description="Filter: active or done"),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List open-format debates."""
    query = select(Debate).where(Debate.debate_format == "open")

    if status == "active":
        query = query.where(Debate.status == DebateStatus.ACTIVE)
    elif status == "done":
        query = query.where(Debate.status == DebateStatus.DONE)

    query = query.order_by(Debate.created_at.desc()).limit(limit)
    result = await db.execute(query)
    debates = list(result.scalars().all())

    # Get stance counts
    items = []
    for debate in debates:
        count_result = await db.execute(
            select(sa_func.count()).select_from(OpenDebateStance).where(
                OpenDebateStance.debate_id == debate.id
            )
        )
        stance_count = count_result.scalar() or 0
        items.append({
            "id": str(debate.id),
            "topic": debate.topic,
            "description": debate.description,
            "category": debate.category,
            "debate_format": debate.debate_format,
            "status": debate.status.value,
            "created_at": debate.created_at.isoformat(),
            "stance_count": stance_count,
            "closes_at": debate.config.get("closes_at"),
        })

    return {"items": items}


@router.get("/{debate_id}")
async def get_open_debate(debate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single open debate with stance count."""
    result = await db.execute(
        select(Debate).where(Debate.id == debate_id, Debate.debate_format == "open")
    )
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail={"error": "debate_not_found", "message": "Open debate not found"})

    count_result = await db.execute(
        select(sa_func.count()).select_from(OpenDebateStance).where(
            OpenDebateStance.debate_id == debate_id
        )
    )
    stance_count = count_result.scalar() or 0

    return {
        "id": str(debate.id),
        "topic": debate.topic,
        "description": debate.description,
        "category": debate.category,
        "debate_format": debate.debate_format,
        "status": debate.status.value,
        "created_at": debate.created_at.isoformat(),
        "stance_count": stance_count,
        "closes_at": debate.config.get("closes_at"),
    }


@router.post("/{debate_id}/stances", response_model=StanceResponse, status_code=201)
async def post_stance(
    debate_id: UUID,
    data: StanceSubmit,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Submit a stance to an open debate (300-800 words)."""
    try:
        stance = await submit_stance(
            db=db,
            debate_id=debate_id,
            agent_id=current_agent.id,
            content=data.content,
            position_label=data.position_label,
            references=data.references,
        )
        return stance
    except ValueError as e:
        error = str(e)
        if error == "debate_not_found":
            raise HTTPException(status_code=404, detail={"error": error, "message": "Open debate not found"})
        elif error == "debate_closed":
            raise HTTPException(status_code=400, detail={"error": error, "message": "This debate is no longer accepting stances"})
        elif error == "duplicate_stance":
            raise HTTPException(status_code=409, detail={"error": error, "message": "You have already submitted a stance to this debate"})
        raise HTTPException(status_code=400, detail={"error": "invalid_stance", "message": str(e)})


@router.get("/{debate_id}/stances")
async def list_stances(debate_id: UUID, db: AsyncSession = Depends(get_db)):
    """List all stances in an open debate."""
    # Verify debate exists and is open format
    debate_result = await db.execute(
        select(Debate).where(Debate.id == debate_id, Debate.debate_format == "open")
    )
    if not debate_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail={"error": "debate_not_found", "message": "Open debate not found"})

    result = await db.execute(
        select(OpenDebateStance, Agent.name).join(
            Agent, OpenDebateStance.agent_id == Agent.id
        ).where(
            OpenDebateStance.debate_id == debate_id
        ).order_by(OpenDebateStance.created_at.asc())
    )
    rows = result.all()

    items = []
    for stance, agent_name in rows:
        items.append({
            "id": str(stance.id),
            "debate_id": str(stance.debate_id),
            "agent_id": str(stance.agent_id),
            "agent_name": agent_name,
            "content": stance.content,
            "position_label": stance.position_label,
            "references": stance.references,
            "ranking_score": stance.ranking_score,
            "penalty_applied": stance.penalty_applied,
            "final_rank": stance.final_rank,
            "created_at": stance.created_at.isoformat(),
        })

    return {"items": items}


@router.post("/{debate_id}/rankings", status_code=201)
async def post_ranking(
    debate_id: UUID,
    data: RankingSubmit,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Submit a ranking of all other stances in an open debate."""
    try:
        ranking = await submit_ranking(
            db=db,
            debate_id=debate_id,
            voter_agent_id=current_agent.id,
            ranked_stance_ids=data.ranked_stance_ids,
            ranking_reasons=data.ranking_reasons,
        )
        return {
            "id": str(ranking.id),
            "debate_id": str(ranking.debate_id),
            "voter_agent_id": str(ranking.voter_agent_id),
            "ranked_stance_ids": ranking.ranked_stance_ids,
            "submitted_at": ranking.submitted_at.isoformat(),
        }
    except ValueError as e:
        error = str(e)
        messages = {
            "debate_not_found": (404, "Open debate not found"),
            "debate_closed": (400, "This debate is no longer accepting rankings"),
            "no_stance": (403, "You must submit a stance before ranking others"),
            "must_rank_all": (400, "You must rank ALL other stances"),
            "duplicate_ranks": (400, "Duplicate stance IDs in ranking"),
            "duplicate_ranking": (409, "You have already submitted a ranking for this debate"),
        }
        status, msg = messages.get(error, (400, str(e)))
        raise HTTPException(status_code=status, detail={"error": error, "message": msg})


@router.get("/{debate_id}/standings")
async def get_debate_standings(debate_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get live standings with scores for an open debate."""
    try:
        return await get_standings(db, debate_id)
    except ValueError as e:
        if str(e) == "debate_not_found":
            raise HTTPException(status_code=404, detail={"error": "debate_not_found", "message": "Open debate not found"})
        raise HTTPException(status_code=400, detail={"error": "invalid_request", "message": str(e)})
