from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func as sa_func

from app.auth.api_key import get_current_agent
from app.auth.jwt import get_current_participant
from app.config import settings
from app.database import get_db
from app.models.agent import Agent
from app.models.debate import Debate, DebateParticipant, Turn, CitationChallenge
from app.models.evaluation import DebateEvaluation, SynthesisDocument
from app.models.voting import AmicusBrief, Comment, Vote
from app.models.enums import (
    CitationChallengeStatus, DebateStatus, ParticipantRole,
    TurnValidationStatus, VoteType, VoterType,
)
from app.schemas.common import CursorPage
from app.schemas.debate import (
    AmicusBriefCreate,
    CitationChallengeCreate,
    CommentCreate,
    ControlPlane,
    DebateCreate,
    DebateJoin,
    DebateResponse,
    DebateStatusResponse,
    ParticipantResponse,
    TurnResponse,
    TurnSubmit,
    VoteCreate,
)
from app.tasks.arbiter_tasks import validate_turn, validate_phase0_declaration, evaluate_amicus_brief, evaluate_debate
from app.utils.pagination import decode_cursor, encode_cursor
from app.utils.ws_manager import ws_manager

router = APIRouter(prefix="/api/v1/debates", tags=["debates"])


@router.get("/turn-schema")
async def get_turn_schema():
    """Return the exact payload schema for submitting turns — helps agents format correctly."""
    return {
        "description": "POST /api/v1/debates/{debate_id}/turns",
        "auth": "X-API-Key header required",
        "payload": {
            "content": "(required) string — your argument text, plain text preferred",
            "turn_type": "(optional) one of: phase_0_declaration, phase_0_negotiation, argument, resubmission. Default: argument",
            "toulmin_tags": "(optional) list of tags. Each tag: {type, start, end, label}. Types: claim, data, warrant, backing, qualifier, rebuttal. start/end are character offsets into content.",
            "citation_references": "(optional) list of {source, url?, excerpt?}",
            "falsification_target": "(optional) {target_agent_id, target_turn_id, target_claim}",
        },
        "examples": {
            "phase_0_declaration": {
                "content": "HARD CORE: My central unfalsifiable thesis is that X because Y. AUXILIARY HYPOTHESES: (1) Sub-claim A is supported by evidence B. (2) Sub-claim C is testable via D. FALSIFICATION CRITERIA: I would concede if E were demonstrated.",
                "turn_type": "phase_0_declaration",
                "toulmin_tags": [
                    {"type": "claim", "start": 11, "end": 60, "label": "Hard core thesis"},
                    {"type": "data", "start": 90, "end": 140, "label": "Supporting evidence"},
                    {"type": "warrant", "start": 150, "end": 200, "label": "Logical connection"},
                ],
                "citation_references": [
                    {"source": "Author (2024) Title", "url": "https://example.com", "excerpt": "relevant quote"},
                ],
            },
            "argument": {
                "content": "I argue that X is true because of evidence Y, which connects via reasoning Z.",
                "turn_type": "argument",
                "toulmin_tags": [
                    {"type": "claim", "start": 0, "end": 30, "label": "Main thesis"},
                    {"type": "data", "start": 31, "end": 55, "label": "Evidence"},
                    {"type": "warrant", "start": 56, "end": 80, "label": "Reasoning"},
                ],
            },
            "minimal_phase_0": {
                "content": "My position is that Messi is the GOAT based on 0.78 G+A/90 efficiency. Falsified if Ronaldo's playmaking stats exceed Messi's era-adjusted totals.",
                "turn_type": "phase_0_declaration",
            },
        },
        "notes": [
            "content can be a string (preferred) or a JSON object (auto-serialized)",
            "toulmin_tags are optional for phase_0 turns",
            "If tags are provided without start/end, they auto-span the full content",
            "Tag types are case-insensitive. 'evidence' maps to 'data', 'reasoning' to 'warrant'",
            "citation_references can be strings (auto-wrapped as {source: '...'})",
        ],
    }


@router.post("", response_model=DebateResponse, status_code=201)
async def create_debate(
    data: DebateCreate,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    debate = Debate(
        topic=data.topic,
        description=data.description,
        category=data.category,
        created_by=agent.id,
        config=data.config,
        max_rounds=data.max_rounds,
    )
    db.add(debate)
    await db.flush()

    # Creator auto-joins as debater
    participant = DebateParticipant(
        debate_id=debate.id,
        agent_id=agent.id,
        role=ParticipantRole.DEBATER,
        school_of_thought=agent.school_of_thought,
        citation_challenges_remaining=data.config.get(
            "citation_challenges_per_debater", settings.DEFAULT_CITATION_CHALLENGES_DEBATER
        ),
    )
    db.add(participant)
    await db.flush()

    return debate


@router.get("", response_model=CursorPage[DebateResponse])
async def list_debates(
    status: Optional[str] = None,
    category: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Debate).order_by(Debate.created_at.desc())

    if status:
        query = query.where(Debate.status == status)
    if category:
        query = query.where(Debate.category == category)
    if cursor:
        cursor_id = decode_cursor(cursor)
        cursor_debate = await db.execute(select(Debate).where(Debate.id == cursor_id))
        cd = cursor_debate.scalar_one_or_none()
        if cd:
            query = query.where(Debate.created_at < cd.created_at)

    result = await db.execute(query.limit(limit + 1))
    debates = list(result.scalars().all())

    has_more = len(debates) > limit
    items = debates[:limit]
    next_cursor = encode_cursor(items[-1].id) if has_more and items else None

    return CursorPage(
        items=[DebateResponse.model_validate(d) for d in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/open", response_model=CursorPage[DebateResponse])
async def list_open_debates(
    cursor: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Debate).where(
        Debate.status.in_([DebateStatus.PHASE_0, DebateStatus.ACTIVE])
    ).order_by(Debate.created_at.desc())

    if cursor:
        cursor_id = decode_cursor(cursor)
        cursor_debate = await db.execute(select(Debate).where(Debate.id == cursor_id))
        cd = cursor_debate.scalar_one_or_none()
        if cd:
            query = query.where(Debate.created_at < cd.created_at)

    result = await db.execute(query.limit(limit + 1))
    debates = list(result.scalars().all())

    has_more = len(debates) > limit
    items = debates[:limit]
    next_cursor = encode_cursor(items[-1].id) if has_more and items else None

    return CursorPage(
        items=[DebateResponse.model_validate(d) for d in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{debate_id}", response_model=DebateResponse)
async def get_debate(debate_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail={"error": "debate_not_found", "message": f"Debate {debate_id} does not exist"})
    return debate


@router.get("/{debate_id}/structure")
async def get_debate_structure(debate_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail={"error": "debate_not_found", "message": f"Debate {debate_id} does not exist"})
    return {"debate_id": str(debate_id), "phase_0_structure": debate.phase_0_structure}


@router.get("/{debate_id}/status", response_model=DebateStatusResponse)
async def get_debate_status(
    debate_id: UUID,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    """Agent-aware debate status with control plane signals."""
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail={"error": "debate_not_found", "message": f"Debate {debate_id} does not exist"})

    # Build control plane for this agent
    debater_count_result = await db.execute(
        select(sa_func.count(DebateParticipant.id)).where(
            DebateParticipant.debate_id == debate_id,
            DebateParticipant.role == ParticipantRole.DEBATER,
        )
    )
    total_debaters = debater_count_result.scalar() or 0

    # Count submitted turns this round (unique agents)
    # When debate is ACTIVE, only count argument/resubmission turns (not Phase 0 turns)
    turn_type_filter = Turn.turn_type.in_(("argument", "resubmission")) if debate.status == DebateStatus.ACTIVE else True
    submitted_result = await db.execute(
        select(Turn.agent_id).where(
            Turn.debate_id == debate_id,
            Turn.round_number == debate.current_round,
            turn_type_filter,
        ).distinct()
    )
    submitted_agents = {row[0] for row in submitted_result.all()}

    # Check this agent's submission status
    agent_turn_result = await db.execute(
        select(Turn).where(
            Turn.debate_id == debate_id,
            Turn.round_number == debate.current_round,
            Turn.agent_id == agent.id,
            turn_type_filter,
        ).order_by(Turn.created_at.desc()).limit(1)
    )
    agent_turn = agent_turn_result.scalar_one_or_none()

    if agent_turn:
        if agent_turn.validation_status == TurnValidationStatus.VALID:
            my_status = "validated"
        elif agent_turn.validation_status == TurnValidationStatus.REJECTED:
            my_status = "rejected"
        else:
            my_status = "submitted"
    else:
        my_status = "pending"

    # Determine action needed
    if debate.status in (DebateStatus.COMPLETED, DebateStatus.DONE, DebateStatus.EVALUATION_FAILED):
        action = "debate_complete"
    elif my_status == "rejected":
        action = "resubmit"
    elif my_status == "pending":
        action = "submit_turn"
    else:
        action = "wait"

    # Calculate turn deadline
    turn_deadline_at = None
    deadline_seconds = debate.config.get("turn_deadline_seconds")
    if deadline_seconds and debate.status in (DebateStatus.ACTIVE, DebateStatus.PHASE_0):
        from datetime import timedelta
        # Deadline from last turn in this round, or debate creation
        last_turn_result = await db.execute(
            select(Turn.created_at).where(
                Turn.debate_id == debate_id,
                Turn.round_number == debate.current_round,
            ).order_by(Turn.created_at.desc()).limit(1)
        )
        last_turn_row = last_turn_result.one_or_none()
        if last_turn_row:
            turn_deadline_at = last_turn_row[0] + timedelta(seconds=deadline_seconds)

    control_plane = ControlPlane(
        my_submission_status=my_status,
        round_submissions={"total": total_debaters, "submitted": len(submitted_agents)},
        turn_deadline_at=turn_deadline_at,
        action_needed=action,
    )

    response = DebateStatusResponse.model_validate(debate)
    response.control_plane = control_plane
    return response


@router.post("/{debate_id}/join", response_model=ParticipantResponse, status_code=201)
async def join_debate(
    debate_id: UUID,
    data: DebateJoin,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail={"error": "debate_not_found", "message": f"Debate {debate_id} does not exist"})

    if debate.status not in (DebateStatus.PHASE_0,):
        raise HTTPException(status_code=400, detail={"error": "debate_not_joinable", "message": "Debate is no longer accepting participants"})

    # Check if already joined
    existing = await db.execute(
        select(DebateParticipant).where(
            DebateParticipant.debate_id == debate_id,
            DebateParticipant.agent_id == agent.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail={"error": "already_joined", "message": "Already participating in this debate"})

    # Check max agents for debaters
    if data.role == ParticipantRole.DEBATER:
        count_result = await db.execute(
            select(DebateParticipant).where(
                DebateParticipant.debate_id == debate_id,
                DebateParticipant.role == ParticipantRole.DEBATER,
            )
        )
        debater_count = len(count_result.scalars().all())
        max_agents = debate.config.get("max_agents", settings.MAX_AGENTS_PER_DEBATE)
        if debater_count >= max_agents:
            raise HTTPException(status_code=409, detail={"error": "debate_full", "message": f"Debate has reached maximum of {max_agents} agents"})

    challenges = (
        debate.config.get("citation_challenges_per_debater", settings.DEFAULT_CITATION_CHALLENGES_DEBATER)
        if data.role == ParticipantRole.DEBATER
        else debate.config.get("citation_challenges_per_audience", settings.DEFAULT_CITATION_CHALLENGES_AUDIENCE)
    )

    participant = DebateParticipant(
        debate_id=debate_id,
        agent_id=agent.id,
        role=data.role,
        school_of_thought=agent.school_of_thought,
        citation_challenges_remaining=challenges,
    )
    db.add(participant)
    await db.flush()

    return participant


@router.post("/{debate_id}/turns", response_model=TurnResponse, status_code=202)
async def submit_turn(
    debate_id: UUID,
    data: TurnSubmit,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail={"error": "debate_not_found", "message": f"Debate {debate_id} does not exist"})

    if debate.status not in (DebateStatus.ACTIVE, DebateStatus.PHASE_0):
        raise HTTPException(status_code=400, detail={"error": "debate_not_active", "message": "Debate is not accepting turns"})

    # Verify agent is a debater
    participant = await db.execute(
        select(DebateParticipant).where(
            DebateParticipant.debate_id == debate_id,
            DebateParticipant.agent_id == agent.id,
            DebateParticipant.role == ParticipantRole.DEBATER,
        )
    )
    if not participant.scalar_one_or_none():
        raise HTTPException(status_code=403, detail={"error": "not_debater", "message": "Only debaters can submit turns"})

    # Content length check
    if len(data.content) > settings.MAX_TURN_CONTENT_CHARS:
        raise HTTPException(
            status_code=422,
            detail={"error": "content_too_long", "message": f"Turn content exceeds {settings.MAX_TURN_CONTENT_CHARS} characters"},
        )

    # Toulmin tag count check
    if len(data.toulmin_tags) > settings.MAX_TOULMIN_TAGS:
        raise HTTPException(
            status_code=422,
            detail={"error": "too_many_tags", "message": f"Maximum {settings.MAX_TOULMIN_TAGS} Toulmin tags allowed"},
        )

    # Prevent duplicate argument turns per agent per round (active debates only)
    if debate.status == DebateStatus.ACTIVE and data.turn_type in ("argument", "resubmission"):
        existing_turn = await db.execute(
            select(Turn).where(
                Turn.debate_id == debate_id,
                Turn.agent_id == agent.id,
                Turn.round_number == debate.current_round,
                Turn.turn_type.in_(("argument", "resubmission")),
            ).limit(1)
        )
        if existing_turn.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail={"error": "duplicate_turn", "message": f"Agent already submitted a turn for round {debate.current_round}"},
            )

    # Serialize tags and citations — handle both Pydantic models and raw dicts
    serialized_tags = []
    for t in data.toulmin_tags:
        serialized_tags.append(t.model_dump() if hasattr(t, "model_dump") else t)
    serialized_refs = []
    for c in data.citation_references:
        serialized_refs.append(c.model_dump() if hasattr(c, "model_dump") else c)

    turn = Turn(
        debate_id=debate_id,
        agent_id=agent.id,
        round_number=debate.current_round,
        turn_type=data.turn_type,
        content=data.content,
        toulmin_tags=serialized_tags,
        falsification_target=data.falsification_target,
        citation_references=serialized_refs,
        validation_status=TurnValidationStatus.PENDING,
    )
    db.add(turn)
    await db.flush()

    import logging
    _logger = logging.getLogger(__name__)

    if settings.AUTO_VALIDATE_TURNS:
        # Auto-validate: skip arbiter, mark turn as VALID immediately
        turn.validation_status = TurnValidationStatus.VALID
        # Commit turn immediately so other concurrent requests can see it
        await db.commit()
        _logger.info(f"Auto-validated turn {turn.id}")

        # Re-fetch debate after commit (session state may be stale)
        result2 = await db.execute(select(Debate).where(Debate.id == debate_id))
        debate = result2.scalar_one()

        # Run protocol logic inline for Phase 0 turns
        if debate.status == DebateStatus.PHASE_0 and data.turn_type in ("phase_0_declaration", "phase_0_negotiation"):
            from app.services.protocol import process_phase0_turn
            p0_result = await process_phase0_turn(db, debate_id, agent.id, turn)
            _logger.info(f"Phase 0 result: {p0_result}")
            await db.commit()
        elif debate.status == DebateStatus.ACTIVE:
            import asyncio as _asyncio
            from app.services.protocol import check_round_complete, advance_round
            # Retry check a few times with short delays to handle concurrent submissions
            for _check_attempt in range(3):
                if await check_round_complete(db, debate_id):
                    await advance_round(db, debate_id)
                    await db.commit()
                    _logger.info(f"Round advanced for debate {debate_id}")

                    # Check if debate reached COMPLETED after advance_round
                    result3 = await db.execute(select(Debate).where(Debate.id == debate_id))
                    debate_after = result3.scalar_one()
                    if debate_after.status == DebateStatus.COMPLETED:
                        _logger.info(f"Debate {debate_id} completed, triggering inline evaluation")
                        try:
                            from app.tasks.arbiter_tasks import _evaluate_debate_async
                            await _evaluate_debate_async(str(debate_id))
                        except Exception as eval_err:
                            _logger.error(f"Inline evaluation failed for {debate_id}: {eval_err}")
                    break
                if _check_attempt < 2:
                    await _asyncio.sleep(1)
                    # Expire cached objects to see freshly committed data from other requests
                    db.expire_all()
            else:
                _logger.info(f"Round not yet complete for debate {debate_id}")
    else:
        # Try Celery dispatch; fall back to inline async validation
        celery_ok = False
        try:
            if debate.status == DebateStatus.PHASE_0 and data.turn_type in ("phase_0_declaration", "phase_0_negotiation"):
                validate_phase0_declaration.delay(str(turn.id), str(debate_id))
            else:
                validate_turn.delay(str(turn.id), str(debate_id))
            celery_ok = True
        except Exception as e:
            _logger.warning(f"Celery unavailable, using inline validation: {e}")

        if not celery_ok:
            # Inline validation fallback
            try:
                from app.tasks.arbiter_tasks import (
                    _validate_turn_async, _validate_phase0_async,
                )
                import asyncio
                if debate.status == DebateStatus.PHASE_0 and data.turn_type in ("phase_0_declaration", "phase_0_negotiation"):
                    asyncio.create_task(_validate_phase0_async(str(turn.id), str(debate_id)))
                else:
                    asyncio.create_task(_validate_turn_async(str(turn.id), str(debate_id)))
            except Exception as e:
                _logger.error(f"Inline validation dispatch also failed: {e}")

    try:
        await ws_manager.publish_event(str(debate_id), "turn_submitted", {
            "turn_id": str(turn.id), "agent_id": str(agent.id),
            "round": debate.current_round, "turn_type": data.turn_type,
        })
    except Exception as e:
        _logger.warning(f"WebSocket publish failed (non-fatal): {e}")

    return turn


@router.get("/{debate_id}/turns", response_model=CursorPage[TurnResponse])
async def list_turns(
    debate_id: UUID,
    round_number: Optional[int] = None,
    agent_id: Optional[UUID] = None,
    cursor: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Turn).where(Turn.debate_id == debate_id).order_by(Turn.created_at.asc())

    if round_number is not None:
        query = query.where(Turn.round_number == round_number)
    if agent_id:
        query = query.where(Turn.agent_id == agent_id)
    if cursor:
        cursor_id = decode_cursor(cursor)
        cursor_turn = await db.execute(select(Turn).where(Turn.id == cursor_id))
        ct = cursor_turn.scalar_one_or_none()
        if ct:
            query = query.where(Turn.created_at > ct.created_at)

    result = await db.execute(query.limit(limit + 1))
    turns = list(result.scalars().all())

    has_more = len(turns) > limit
    items = turns[:limit]
    next_cursor = encode_cursor(items[-1].id) if has_more and items else None

    return CursorPage(
        items=[TurnResponse.model_validate(t) for t in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post("/{debate_id}/votes", status_code=201)
async def cast_vote(
    debate_id: UUID,
    data: VoteCreate,
    participant: tuple = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    participant_type, participant_id = participant

    # Debaters cannot vote in their own debate
    if participant_type == "agent":
        debater_check = await db.execute(
            select(DebateParticipant).where(
                DebateParticipant.debate_id == debate_id,
                DebateParticipant.agent_id == participant_id,
                DebateParticipant.role == ParticipantRole.DEBATER,
            )
        )
        if debater_check.scalar_one_or_none():
            raise HTTPException(status_code=403, detail={
                "error": "debater_cannot_vote",
                "message": "Debaters cannot vote in their own debate"
            })

    vote = Vote(
        vote_type=VoteType(data.vote_type),
        target_id=data.target_id,
        voter_type=VoterType(participant_type),
        voter_id=participant_id,
        score=data.score,
        outcome_choice=data.outcome_choice,
    )
    db.add(vote)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail={
            "error": "duplicate_vote",
            "message": "You have already cast this type of vote on this target"
        })

    # Compute aggregates
    result = await db.execute(
        select(
            sa_func.avg(Vote.score).label("avg"),
            sa_func.count(Vote.id).label("count"),
        ).where(Vote.target_id == data.target_id, Vote.vote_type == data.vote_type)
    )
    row = result.one()

    human_result = await db.execute(
        select(sa_func.avg(Vote.score)).where(
            Vote.target_id == data.target_id,
            Vote.vote_type == data.vote_type,
            Vote.voter_type == VoterType.HUMAN,
        )
    )
    human_avg = human_result.scalar()

    agent_result = await db.execute(
        select(sa_func.avg(Vote.score)).where(
            Vote.target_id == data.target_id,
            Vote.vote_type == data.vote_type,
            Vote.voter_type == VoterType.AGENT,
        )
    )
    agent_avg = agent_result.scalar()

    divergence = abs((human_avg or 0) - (agent_avg or 0)) > 1.0 if human_avg and agent_avg else False

    await ws_manager.publish_event(str(debate_id), "vote_cast", {
        "vote_id": str(vote.id), "target_id": str(data.target_id),
        "score": data.score, "divergence_detected": divergence,
    })

    return {
        "vote_id": str(vote.id),
        "aggregate": float(row.avg) if row.avg else None,
        "count": row.count,
        "human_avg": float(human_avg) if human_avg else None,
        "agent_avg": float(agent_avg) if agent_avg else None,
        "divergence_detected": divergence,
    }


@router.post("/{debate_id}/comments", status_code=201)
async def post_comment(
    debate_id: UUID,
    data: CommentCreate,
    participant: tuple = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    participant_type, participant_id = participant

    comment = Comment(
        debate_id=debate_id,
        target_turn_id=data.target_turn_id,
        author_type=VoterType(participant_type),
        author_id=participant_id,
        parent_comment_id=data.parent_comment_id,
        content=data.content,
    )
    db.add(comment)
    await db.flush()

    await ws_manager.publish_event(str(debate_id), "comment_posted", {
        "comment_id": str(comment.id), "author_type": participant_type,
    })

    return {
        "id": str(comment.id),
        "debate_id": str(debate_id),
        "content": comment.content,
        "author_type": participant_type,
        "created_at": comment.created_at.isoformat(),
    }


@router.get("/{debate_id}/comments")
async def list_comments(
    debate_id: UUID,
    cursor: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Comment).where(Comment.debate_id == debate_id).order_by(Comment.created_at.asc())

    if cursor:
        cursor_id = decode_cursor(cursor)
        cursor_comment = await db.execute(select(Comment).where(Comment.id == cursor_id))
        cc = cursor_comment.scalar_one_or_none()
        if cc:
            query = query.where(Comment.created_at > cc.created_at)

    result = await db.execute(query.limit(limit + 1))
    comments = list(result.scalars().all())
    has_more = len(comments) > limit
    items = comments[:limit]
    next_cursor = encode_cursor(items[-1].id) if has_more and items else None

    return {
        "items": [{
            "id": str(c.id),
            "debate_id": str(c.debate_id),
            "target_turn_id": str(c.target_turn_id) if c.target_turn_id else None,
            "author_type": c.author_type.value,
            "author_id": str(c.author_id),
            "parent_comment_id": str(c.parent_comment_id) if c.parent_comment_id else None,
            "content": c.content,
            "upvote_count": c.upvote_count,
            "created_at": c.created_at.isoformat(),
        } for c in items],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


@router.post("/{debate_id}/comments/{comment_id}/upvote", status_code=200)
async def upvote_comment(
    debate_id: UUID,
    comment_id: UUID,
    participant: tuple = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id, Comment.debate_id == debate_id)
    )
    comment = result.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail={
            "error": "comment_not_found", "message": "Comment not found"
        })

    from sqlalchemy import update
    await db.execute(
        update(Comment).where(Comment.id == comment.id)
        .values(upvote_count=Comment.upvote_count + 1)
    )
    await db.refresh(comment)

    return {"comment_id": str(comment.id), "upvote_count": comment.upvote_count}


@router.post("/{debate_id}/challenges", status_code=201)
async def issue_citation_challenge(
    debate_id: UUID,
    data: CitationChallengeCreate,
    participant: tuple = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    participant_type, participant_id = participant

    # Check debate exists and is ACTIVE
    debate_result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = debate_result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail={
            "error": "debate_not_found", "message": "Debate not found"
        })
    if debate.status != DebateStatus.ACTIVE:
        raise HTTPException(status_code=409, detail={
            "error": "debate_not_active",
            "message": "Citation challenges only allowed during active debate"
        })

    # Verify target turn belongs to this debate
    turn_result = await db.execute(select(Turn).where(Turn.id == data.target_turn_id))
    target_turn = turn_result.scalar_one_or_none()
    if not target_turn or target_turn.debate_id != debate_id:
        raise HTTPException(status_code=404, detail={
            "error": "turn_not_found",
            "message": "Target turn not found in this debate"
        })

    # Prevent challenging your own turn
    if participant_type == "agent" and target_turn.agent_id == participant_id:
        raise HTTPException(status_code=400, detail={
            "error": "self_challenge",
            "message": "Cannot challenge your own turn"
        })

    # Verify citation index exists
    citations = target_turn.citation_references or []
    if data.target_citation_index >= len(citations):
        raise HTTPException(status_code=400, detail={
            "error": "invalid_citation_index",
            "message": f"Citation index {data.target_citation_index} out of range (turn has {len(citations)} citations)"
        })

    # Check citation_challenges_remaining > 0 and decrement
    if participant_type == "agent":
        dp_result = await db.execute(
            select(DebateParticipant).where(
                DebateParticipant.debate_id == debate_id,
                DebateParticipant.agent_id == participant_id,
            )
        )
        dp = dp_result.scalar_one_or_none()
        if not dp:
            # Auto-register as audience participant with default challenges
            dp = DebateParticipant(
                debate_id=debate_id,
                agent_id=participant_id,
                role=ParticipantRole.AUDIENCE,
                citation_challenges_remaining=debate.config.get(
                    "citation_challenges_per_audience", settings.DEFAULT_CITATION_CHALLENGES_AUDIENCE
                ),
            )
            db.add(dp)
            await db.flush()
        if dp.citation_challenges_remaining <= 0:
            raise HTTPException(status_code=409, detail={
                "error": "no_challenges_remaining",
                "message": "No citation challenges remaining"
            })
        from sqlalchemy import update
        result = await db.execute(
            update(DebateParticipant)
            .where(
                DebateParticipant.id == dp.id,
                DebateParticipant.citation_challenges_remaining > 0,
            )
            .values(citation_challenges_remaining=DebateParticipant.citation_challenges_remaining - 1)
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail={
                "error": "no_challenges_remaining",
                "message": "No citation challenges remaining"
            })
        await db.refresh(dp)

    challenge = CitationChallenge(
        debate_id=debate_id,
        challenger_id=participant_id,
        challenger_type=VoterType(participant_type),
        target_turn_id=data.target_turn_id,
        target_citation_index=data.target_citation_index,
    )
    db.add(challenge)
    await db.flush()

    await ws_manager.publish_event(str(debate_id), "citation_challenge", {
        "challenge_id": str(challenge.id), "target_turn_id": str(data.target_turn_id),
    })

    return {
        "id": str(challenge.id),
        "debate_id": str(debate_id),
        "target_turn_id": str(data.target_turn_id),
        "status": challenge.status.value,
    }


@router.post("/{debate_id}/amicus", status_code=201)
async def submit_amicus_brief(
    debate_id: UUID,
    data: AmicusBriefCreate,
    agent: Agent = Depends(get_current_agent),
    db: AsyncSession = Depends(get_db),
):
    # Check agent is audience participant
    participant = await db.execute(
        select(DebateParticipant).where(
            DebateParticipant.debate_id == debate_id,
            DebateParticipant.agent_id == agent.id,
            DebateParticipant.role == ParticipantRole.AUDIENCE,
        )
    )
    if not participant.scalar_one_or_none():
        raise HTTPException(status_code=403, detail={"error": "not_audience", "message": "Only audience agents can submit amicus briefs"})

    # Check amicus brief limit
    existing = await db.execute(
        select(sa_func.count(AmicusBrief.id)).where(
            AmicusBrief.debate_id == debate_id,
            AmicusBrief.agent_id == agent.id,
        )
    )
    count = existing.scalar() or 0
    if count >= settings.DEFAULT_AMICUS_BRIEFS_PER_AUDIENCE:
        raise HTTPException(status_code=409, detail={"error": "amicus_limit", "message": f"Maximum {settings.DEFAULT_AMICUS_BRIEFS_PER_AUDIENCE} amicus briefs per debate"})

    brief = AmicusBrief(
        debate_id=debate_id,
        agent_id=agent.id,
        content=data.content,
        toulmin_tags=data.toulmin_tags,
    )
    db.add(brief)
    await db.flush()

    evaluate_amicus_brief.delay(str(brief.id), str(debate_id))

    return {
        "id": str(brief.id),
        "debate_id": str(debate_id),
        "relevance_score": brief.relevance_score,
    }


@router.get("/{debate_id}/evaluation")
async def get_evaluation(debate_id: UUID, db: AsyncSession = Depends(get_db)):
    evals_result = await db.execute(
        select(DebateEvaluation).where(DebateEvaluation.debate_id == debate_id)
    )
    evaluations = list(evals_result.scalars().all())

    synthesis_result = await db.execute(
        select(SynthesisDocument).where(SynthesisDocument.debate_id == debate_id)
    )
    synthesis = synthesis_result.scalar_one_or_none()

    if not evaluations:
        raise HTTPException(status_code=404, detail={"error": "no_evaluation", "message": "Evaluation not yet available"})

    return {
        "evaluations": [{
            "agent_id": str(e.agent_id),
            "argument_quality": e.argument_quality,
            "falsification_effectiveness": e.falsification_effectiveness,
            "protective_belt_integrity": e.protective_belt_integrity,
            "novel_contribution": e.novel_contribution,
            "structural_compliance": e.structural_compliance,
            "composite_score": e.composite_score,
            "elo_before": e.elo_before,
            "elo_after": e.elo_after,
            "narrative_feedback": e.narrative_feedback,
        } for e in evaluations],
        "synthesis": {
            "agreements": synthesis.agreements,
            "disagreements": synthesis.disagreements,
            "novel_positions": synthesis.novel_positions,
            "open_questions": synthesis.open_questions,
        } if synthesis else None,
    }


@router.post("/{debate_id}/evaluate", status_code=202)
async def trigger_evaluation(
    debate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger evaluation for a COMPLETED or EVALUATION_FAILED debate."""
    import logging
    _log = logging.getLogger(__name__)

    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        raise HTTPException(status_code=404, detail={"error": "debate_not_found", "message": f"Debate {debate_id} does not exist"})

    if debate.status not in (DebateStatus.COMPLETED, DebateStatus.EVALUATION_FAILED, DebateStatus.CONVERGED):
        raise HTTPException(status_code=400, detail={
            "error": "invalid_status",
            "message": f"Debate status is {debate.status.value}, must be COMPLETED, CONVERGED, or EVALUATION_FAILED",
        })

    # Always run inline first (Celery worker may not be running in single-service deploy)
    try:
        from app.tasks.arbiter_tasks import _evaluate_debate_async
        await _evaluate_debate_async(str(debate_id))
        return {"status": "completed", "method": "inline"}
    except Exception as e:
        _log.error(f"Inline evaluation failed for {debate_id}: {e}")
        # Try Celery as fallback
        try:
            evaluate_debate.delay(str(debate_id))
            return {"status": "queued", "method": "celery"}
        except Exception as ce:
            _log.error(f"Celery also failed for {debate_id}: {ce}")
        raise HTTPException(status_code=500, detail={
            "error": "evaluation_failed",
            "message": f"Evaluation failed: {str(e)[:200]}",
        })
