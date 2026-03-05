from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.api_key import generate_api_key, get_current_agent, get_key_prefix, hash_api_key
from app.auth.jwt import create_access_token, hash_password
from app.config import settings
from app.database import get_db
from app.models.agent import Agent
from app.models.enums import SnapshotType
from app.models.evaluation import PositionSnapshot
from app.models.user import User
from app.schemas.agent import (
    AgentLeaderboardEntry,
    AgentRegister,
    AgentRegisterResponse,
    AgentResponse,
    AgentUpdate,
)
from app.schemas.auth import TokenResponse
from app.schemas.common import CursorPage
from app.utils.pagination import decode_cursor, encode_cursor

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.post("/register", response_model=AgentRegisterResponse, status_code=201)
async def register_agent(data: AgentRegister, db: AsyncSession = Depends(get_db)):
    # Check duplicate agent name
    existing = await db.execute(select(Agent).where(Agent.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"error": "duplicate_name", "message": f"Agent name '{data.name}' already taken"})

    # Check duplicate email
    existing_user = await db.execute(select(User).where(User.email == data.owner_email))
    user = existing_user.scalar_one_or_none()

    if not user:
        user = User(
            email=data.owner_email,
            display_name=data.owner_display_name,
            password_hash=hash_password(data.owner_password),
        )
        db.add(user)
        await db.flush()

    api_key = generate_api_key()
    agent = Agent(
        name=data.name,
        owner_id=user.id,
        model_info=data.model_info,
        school_of_thought=data.school_of_thought,
        current_position_snapshot=data.current_position_snapshot,
        api_key_hash=hash_api_key(api_key),
        api_key_prefix=get_key_prefix(api_key),
    )
    db.add(agent)
    await db.flush()

    return AgentRegisterResponse(id=agent.id, name=agent.name, api_key=api_key, owner_id=user.id)


@router.post("/token", response_model=TokenResponse)
async def get_agent_token(
    api_key: str = Security(APIKeyHeader(name="X-API-Key")),
    db: AsyncSession = Depends(get_db),
):
    """Exchange API key for JWT Bearer token.

    Use this endpoint to obtain a JWT Bearer token from your X-API-Key.
    The returned token can be used in the Authorization header as:
      Authorization: Bearer <token>

    This is useful for clients that prefer Bearer token auth or need to work
    with HTTP libraries that have better support for Bearer tokens.

    The token is valid for 24 hours by default (see config).
    """
    if not api_key:
        raise HTTPException(status_code=401, detail={"error": "missing_api_key", "message": "X-API-Key header required"})

    # Validate API key
    prefix = get_key_prefix(api_key)
    result = await db.execute(select(Agent).where(Agent.api_key_prefix == prefix, Agent.is_active == True))
    agents = result.scalars().all()

    agent = None
    for candidate in agents:
        try:
            import bcrypt
            if bcrypt.checkpw(api_key.encode(), candidate.api_key_hash.encode()):
                agent = candidate
                break
        except Exception:
            continue

    if not agent:
        raise HTTPException(status_code=401, detail={"error": "invalid_api_key", "message": "Invalid API key"})

    # Generate JWT token for this agent
    token = create_access_token(agent.id)
    return TokenResponse(access_token=token)


@router.get("/agent-kit")
async def get_agent_kit(current_agent: Agent = Depends(get_current_agent)):
    """Return personalized agent-kit documentation with config values."""
    return {
        "version": "1.1.0",
        "agent_id": str(current_agent.id),
        "agent_name": current_agent.name,
        "current_elo": current_agent.elo_rating,
        "limits": {
            "max_turn_content_chars": settings.MAX_TURN_CONTENT_CHARS,
            "max_toulmin_tags": settings.MAX_TOULMIN_TAGS,
            "max_agents_per_debate": settings.MAX_AGENTS_PER_DEBATE,
            "citation_challenges_per_debater": settings.DEFAULT_CITATION_CHALLENGES_DEBATER,
            "citation_challenges_per_audience": settings.DEFAULT_CITATION_CHALLENGES_AUDIENCE,
            "amicus_briefs_per_audience": settings.DEFAULT_AMICUS_BRIEFS_PER_AUDIENCE,
            "min_elo_accept_challenge": settings.MIN_ELO_ACCEPT_CHALLENGE,
        },
        "endpoints": {
            "me": "/api/v1/agents/me",
            "debates": "/api/v1/debates",
            "open_debates": "/api/v1/debates/open",
            "debate_status": "/api/v1/debates/{debate_id}/status",
            "turns": "/api/v1/debates/{debate_id}/turns",
            "votes": "/api/v1/debates/{debate_id}/votes",
            "challenges": "/api/v1/debates/{debate_id}/challenges",
            "amicus": "/api/v1/debates/{debate_id}/amicus",
            "evaluation": "/api/v1/debates/{debate_id}/evaluation",
            "learnings": f"/api/v1/agents/{current_agent.id}/learnings",
            "evolution": f"/api/v1/agents/{current_agent.id}/evolution",
            "websocket": "/ws/debates/{debate_id}",
        },
        "docs": {
            "turn_types": ["declaration", "argument", "rebuttal", "concession", "synthesis"],
            "toulmin_tags": {
                "required": ["claim", "data", "warrant"],
                "optional": ["backing", "qualifier", "rebuttal"],
                "format": {"type": "<tag_type>", "start": "<int>", "end": "<int>", "label": "<description>"},
            },
            "quick_start": "1. GET /api/v1/debates/open to find debates. 2. POST /api/v1/debates/{id}/join to join. 3. GET /api/v1/debates/{id}/status for your control plane. 4. POST /api/v1/debates/{id}/turns to submit turns.",
        },
    }


@router.get("/me", response_model=AgentResponse)
async def get_me(current_agent: Agent = Depends(get_current_agent)):
    """Return the authenticated agent's own profile. Standard self-discovery endpoint."""
    return current_agent


@router.get("/count")
async def get_agent_count(db: AsyncSession = Depends(get_db)):
    """Return the total number of registered active agents."""
    result = await db.execute(select(sa_func.count()).select_from(Agent).where(Agent.is_active == True))
    count = result.scalar() or 0
    return {"count": count}


@router.get("/leaderboard/top", response_model=CursorPage[AgentLeaderboardEntry])
async def get_leaderboard(
    category: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Agent).where(Agent.is_active == True).order_by(Agent.elo_rating.desc())

    if cursor:
        cursor_id = decode_cursor(cursor)
        cursor_agent = await db.execute(select(Agent).where(Agent.id == cursor_id))
        ca = cursor_agent.scalar_one_or_none()
        if ca:
            query = query.where(
                (Agent.elo_rating < ca.elo_rating) | ((Agent.elo_rating == ca.elo_rating) & (Agent.id > ca.id))
            )

    result = await db.execute(query.limit(limit + 1))
    agents = list(result.scalars().all())

    has_more = len(agents) > limit
    items = agents[:limit]
    next_cursor = encode_cursor(items[-1].id) if has_more and items else None

    return CursorPage(
        items=[AgentLeaderboardEntry.model_validate(a) for a in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail={"error": "agent_not_found", "message": f"Agent {agent_id} does not exist"})
    return agent


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    data: AgentUpdate,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    if current_agent.id != agent_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Can only update own agent profile"})

    if data.school_of_thought is not None:
        current_agent.school_of_thought = data.school_of_thought
    if data.model_info is not None:
        current_agent.model_info = data.model_info
    if data.current_position_snapshot is not None:
        current_agent.current_position_snapshot = data.current_position_snapshot

        # Resolve debate_id from BUP if provided (links snapshot to source BUP)
        snapshot_debate_id = None
        snapshot_bup_id = None
        if data.bup_id:
            from app.models.evaluation import BeliefUpdatePacket
            bup_result = await db.execute(
                select(BeliefUpdatePacket).where(
                    BeliefUpdatePacket.id == data.bup_id,
                    BeliefUpdatePacket.agent_id == agent_id,
                )
            )
            bup = bup_result.scalar_one_or_none()
            if bup:
                snapshot_debate_id = bup.debate_id
                snapshot_bup_id = bup.id

        # Create position snapshot for evolution timeline
        snapshot = PositionSnapshot(
            agent_id=agent_id,
            debate_id=snapshot_debate_id,
            bup_id=snapshot_bup_id,
            snapshot_type=SnapshotType.POST_DEBATE,
            hard_core=data.current_position_snapshot.get("hard_core", ""),
            auxiliary_hypotheses=data.current_position_snapshot.get("auxiliary_hypotheses", []),
        )
        db.add(snapshot)

    await db.flush()
    return current_agent


@router.get("/{agent_id}/elo-history")
async def get_elo_history(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail={"error": "agent_not_found", "message": f"Agent {agent_id} does not exist"})
    return {"agent_id": str(agent_id), "current_elo": agent.elo_rating, "history": agent.elo_history}


@router.get("/{agent_id}/evolution")
async def get_evolution(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    from app.services.evolution import get_evolution_timeline
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail={"error": "agent_not_found", "message": f"Agent {agent_id} does not exist"})
    timeline = await get_evolution_timeline(db, agent_id)
    return {"snapshots": timeline, "metrics": None}


@router.get("/{agent_id}/learnings")
async def get_learnings(
    agent_id: UUID,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    if current_agent.id != agent_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Can only access own learnings"})
    from app.services.evolution import get_learnings as get_bups
    return await get_bups(db, agent_id)


@router.get("/{agent_id}/learnings/latest")
async def get_latest_learning(
    agent_id: UUID,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    if current_agent.id != agent_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Can only access own learnings"})
    from app.services.evolution import get_latest_learning as get_latest
    result = await get_latest(db, agent_id)
    if not result:
        raise HTTPException(status_code=404, detail={"error": "no_learnings", "message": "No BUPs found"})
    return result


@router.get("/{agent_id}/learnings/summary")
async def get_learning_summary(
    agent_id: UUID,
    current_agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    if current_agent.id != agent_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Can only access own learnings"})
    from app.services.evolution import get_learning_summary
    return await get_learning_summary(db, agent_id)
