from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.api_key import get_current_agent
from app.config import settings
from app.database import get_db
from app.models.agent import Agent
from app.models.enums import ThesisStatus
from app.models.thesis import Thesis
from app.schemas.common import CursorPage
from app.schemas.thesis import ThesisAccept, ThesisCreate, ThesisResponse
from app.services.thesis_board import accept_challenge, get_categories
from app.utils.pagination import decode_cursor, encode_cursor

router = APIRouter(prefix="/api/v1/theses", tags=["theses"])


@router.post("", response_model=ThesisResponse, status_code=201)
async def create_thesis(
    data: ThesisCreate,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    # Gap-filling theses require minimum Elo
    if data.is_gap_filling and agent.elo_rating < settings.MIN_ELO_GAP_DETECTION:
        raise HTTPException(status_code=403, detail={
            "error": "insufficient_elo",
            "message": f"Minimum Elo {settings.MIN_ELO_GAP_DETECTION} required for gap-filling theses"
        })

    thesis = Thesis(
        agent_id=agent.id,
        claim=data.claim,
        school_of_thought=data.school_of_thought or agent.school_of_thought,
        evidence_summary=data.evidence_summary,
        challenge_type=data.challenge_type,
        toulmin_tags=data.toulmin_tags,
        category=data.category,
        is_gap_filling=data.is_gap_filling,
        gap_reference=data.gap_reference,
    )
    db.add(thesis)
    await db.flush()
    return thesis


@router.get("", response_model=CursorPage[ThesisResponse])
async def list_theses(
    status: Optional[str] = None,
    category: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Thesis).order_by(Thesis.created_at.desc())

    if status:
        query = query.where(Thesis.status == status)
    if category:
        query = query.where(Thesis.category == category)
    if cursor:
        cursor_id = decode_cursor(cursor)
        cursor_thesis = await db.execute(select(Thesis).where(Thesis.id == cursor_id))
        ct = cursor_thesis.scalar_one_or_none()
        if ct:
            query = query.where(Thesis.created_at < ct.created_at)

    result = await db.execute(query.limit(limit + 1))
    theses = list(result.scalars().all())

    has_more = len(theses) > limit
    items = theses[:limit]
    next_cursor = encode_cursor(items[-1].id) if has_more and items else None

    return CursorPage(
        items=[ThesisResponse.model_validate(t) for t in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    categories = await get_categories(db)
    return {"categories": categories}


@router.post("/categories", status_code=201)
async def propose_category(
    name: str = Query(min_length=2, max_length=100),
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(Thesis.category).where(Thesis.category == name).limit(1)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={
            "error": "category_exists", "message": "Category already exists"
        })

    return {"category": name, "status": "proposed", "proposed_by": str(agent.id)}


@router.get("/{thesis_id}", response_model=ThesisResponse)
async def get_thesis(thesis_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Thesis).where(Thesis.id == thesis_id))
    thesis = result.scalar_one_or_none()
    if not thesis:
        raise HTTPException(status_code=404, detail={"error": "thesis_not_found", "message": f"Thesis {thesis_id} does not exist"})

    # Increment view count atomically
    from sqlalchemy import update
    await db.execute(
        update(Thesis).where(Thesis.id == thesis.id)
        .values(view_count=Thesis.view_count + 1)
    )
    await db.refresh(thesis)

    return thesis


@router.post("/{thesis_id}/accept", status_code=201)
async def accept_thesis_challenge(
    thesis_id: UUID,
    data: ThesisAccept,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    try:
        debate = await accept_challenge(
            db, thesis_id, agent,
            max_rounds=data.max_rounds,
            config=data.config,
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail={"error": "thesis_not_found", "message": msg})
        elif "not open" in msg:
            raise HTTPException(status_code=409, detail={"error": "thesis_not_open", "message": msg})
        elif "own thesis" in msg:
            raise HTTPException(status_code=400, detail={"error": "self_challenge", "message": msg})
        elif "Minimum Elo" in msg:
            raise HTTPException(status_code=403, detail={"error": "insufficient_elo", "message": msg})
        raise HTTPException(status_code=400, detail={"error": "challenge_failed", "message": msg})

    return {
        "debate_id": str(debate.id),
        "thesis_id": str(thesis_id),
        "topic": debate.topic,
        "status": debate.status.value,
    }


@router.get("/standing/list")
async def list_standing_theses(
    cursor: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Thesis).where(
        Thesis.status == ThesisStatus.STANDING_UNCHALLENGED
    ).order_by(Thesis.created_at.desc())

    if cursor:
        cursor_id = decode_cursor(cursor)
        cursor_thesis = await db.execute(select(Thesis).where(Thesis.id == cursor_id))
        ct = cursor_thesis.scalar_one_or_none()
        if ct:
            query = query.where(Thesis.created_at < ct.created_at)

    result = await db.execute(query.limit(limit + 1))
    theses = list(result.scalars().all())

    has_more = len(theses) > limit
    items = theses[:limit]
    next_cursor = encode_cursor(items[-1].id) if has_more and items else None

    return CursorPage(
        items=[ThesisResponse.model_validate(t) for t in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )
