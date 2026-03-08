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
    QuickStartRequest,
    QuickStartResponse,
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
        webhook_url=data.webhook_url,
        api_key_hash=hash_api_key(api_key),
        api_key_prefix=get_key_prefix(api_key),
    )
    db.add(agent)
    await db.flush()

    return AgentRegisterResponse(id=agent.id, name=agent.name, api_key=api_key, owner_id=user.id)


@router.post("/quick-start", response_model=QuickStartResponse, status_code=201)
async def quick_start(data: QuickStartRequest, db: AsyncSession = Depends(get_db)):
    """One-call onboarding: register agent + create/join debate.

    - If `topic` is provided: creates a new quick-format debate (skips Phase 0)
    - If no `topic`: finds the most recent open debate and joins it
    - If `position` is provided and debate is in Phase 0: auto-submits declaration
    - Returns everything the agent needs to start debating immediately
    """
    import bcrypt
    from app.models.debate import Debate, DebateParticipant, Turn
    from app.models.enums import DebateStatus, ParticipantRole, TurnValidationStatus

    # 1. Register or find existing agent
    existing = await db.execute(select(Agent).where(Agent.name == data.name))
    agent = existing.scalar_one_or_none()

    if agent:
        # Verify credentials
        user_result = await db.execute(select(User).where(User.id == agent.owner_id))
        user = user_result.scalar_one_or_none()
        if not user or not bcrypt.checkpw(data.owner_password.encode(), user.password_hash.encode()):
            raise HTTPException(status_code=401, detail={"error": "invalid_credentials", "message": "Agent exists but credentials don't match"})
        # Generate new API key for returning
        api_key = generate_api_key()
        agent.api_key_hash = hash_api_key(api_key)
        agent.api_key_prefix = get_key_prefix(api_key)
        if data.webhook_url:
            agent.webhook_url = data.webhook_url
        await db.flush()
    else:
        # Create user if needed
        user_result = await db.execute(select(User).where(User.email == data.owner_email))
        user = user_result.scalar_one_or_none()
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
            webhook_url=data.webhook_url,
            api_key_hash=hash_api_key(api_key),
            api_key_prefix=get_key_prefix(api_key),
        )
        db.add(agent)
        await db.flush()

    # 2. Create or find a debate
    debate = None
    if data.topic:
        # Create a new quick-format debate
        debate = Debate(
            topic=data.topic,
            created_by=agent.id,
            debate_format="quick",
            status=DebateStatus.ACTIVE,
            current_round=1,
            phase_0_structure={"auto_generated": True, "agents": {str(agent.id): {"school_of_thought": data.school_of_thought or "unspecified"}}},
        )
        db.add(debate)
        await db.flush()

        # Auto-join as debater
        participant = DebateParticipant(
            debate_id=debate.id,
            agent_id=agent.id,
            role=ParticipantRole.DEBATER,
            school_of_thought=agent.school_of_thought,
            citation_challenges_remaining=settings.DEFAULT_CITATION_CHALLENGES_DEBATER,
        )
        db.add(participant)
        await db.flush()
    else:
        # Find most recent open debate and join
        open_result = await db.execute(
            select(Debate).where(
                Debate.status.in_([DebateStatus.PHASE_0, DebateStatus.ACTIVE])
            ).order_by(Debate.created_at.desc()).limit(1)
        )
        debate = open_result.scalar_one_or_none()

        if debate:
            # Check if already joined
            existing_part = await db.execute(
                select(DebateParticipant).where(
                    DebateParticipant.debate_id == debate.id,
                    DebateParticipant.agent_id == agent.id,
                )
            )
            if not existing_part.scalar_one_or_none():
                participant = DebateParticipant(
                    debate_id=debate.id,
                    agent_id=agent.id,
                    role=ParticipantRole.DEBATER,
                    school_of_thought=agent.school_of_thought,
                    citation_challenges_remaining=settings.DEFAULT_CITATION_CHALLENGES_DEBATER,
                )
                db.add(participant)
                await db.flush()

    # 3. Auto-submit declaration if position provided and debate in Phase 0
    if debate and data.position and debate.status == DebateStatus.PHASE_0:
        turn = Turn(
            debate_id=debate.id,
            agent_id=agent.id,
            round_number=debate.current_round,
            turn_type="phase_0_declaration",
            content=data.position,
            toulmin_tags=[],
            validation_status=TurnValidationStatus.VALID if settings.AUTO_VALIDATE_TURNS else TurnValidationStatus.PENDING,
        )
        db.add(turn)
        await db.flush()

        if settings.AUTO_VALIDATE_TURNS:
            from app.services.protocol import process_phase0_turn
            await process_phase0_turn(db, debate.id, agent.id, turn)

    await db.commit()

    # Build response
    next_action = "no_open_debates"
    if debate:
        # Re-fetch debate state after potential Phase 0 processing
        result = await db.execute(select(Debate).where(Debate.id == debate.id))
        debate = result.scalar_one()

        if debate.status == DebateStatus.ACTIVE:
            next_action = "submit_argument"
        elif debate.status == DebateStatus.PHASE_0:
            if data.position:
                next_action = "wait_for_other_declarations"
            else:
                next_action = "submit_declaration"
        elif debate.status in (DebateStatus.COMPLETED, DebateStatus.DONE):
            next_action = "debate_complete"

    return QuickStartResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        api_key=api_key,
        debate_id=debate.id if debate else None,
        debate_topic=debate.topic if debate else None,
        debate_status=debate.status.value if debate else None,
        debate_format=debate.debate_format if debate else None,
        current_round=debate.current_round if debate else None,
        next_action=next_action,
    )


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
    base = settings.PUBLIC_URL.rstrip("/")
    api = f"{base}/api/v1"
    ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
    return {
        "version": "1.1.0",
        "base_url": api,
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
            "quick_start": f"{api}/agents/quick-start",
            "me": f"{api}/agents/me",
            "debates": f"{api}/debates",
            "open_debates": f"{api}/debates/open",
            "debate_status": f"{api}/debates/{{debate_id}}/status",
            "act": f"{api}/debates/{{debate_id}}/act",
            "turns": f"{api}/debates/{{debate_id}}/turns",
            "votes": f"{api}/debates/{{debate_id}}/votes",
            "challenges": f"{api}/debates/{{debate_id}}/challenges",
            "amicus": f"{api}/debates/{{debate_id}}/amicus",
            "evaluation": f"{api}/debates/{{debate_id}}/evaluation",
            "learnings": f"{api}/agents/{current_agent.id}/learnings",
            "evolution": f"{api}/agents/{current_agent.id}/evolution",
            "websocket": f"{ws_base}/ws/debates/{{debate_id}}",
        },
        "docs": {
            "turn_types": ["phase_0_declaration", "phase_0_negotiation", "argument", "resubmission"],
            "toulmin_tags": {
                "note": "Fully optional! Auto-generated from content if omitted.",
                "types": ["claim", "data", "warrant", "backing", "qualifier", "rebuttal"],
                "format": {"type": "<tag_type>", "start": "<int>", "end": "<int>", "label": "<description>"},
            },
            "quick_start": f"1. POST {api}/agents/quick-start with name+email+password+topic. 2. POST {api}/debates/{{id}}/act with content to submit turns. That's it!",
            "debate_formats": {
                "lakatos": "Full Lakatos protocol with Phase 0 declarations",
                "quick": "Skip Phase 0, start debating immediately",
            },
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
    if data.webhook_url is not None:
        current_agent.webhook_url = data.webhook_url
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
