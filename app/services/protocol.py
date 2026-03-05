import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate import Debate, DebateParticipant, Turn
from app.models.enums import DebateStatus, ParticipantRole, SnapshotType, ThesisStatus, TurnValidationStatus
from app.models.evaluation import PositionSnapshot
from app.models.thesis import Thesis

logger = logging.getLogger(__name__)


async def get_debater_count(db: AsyncSession, debate_id: UUID) -> int:
    result = await db.execute(
        select(sa_func.count(DebateParticipant.id)).where(
            DebateParticipant.debate_id == debate_id,
            DebateParticipant.role == ParticipantRole.DEBATER,
        )
    )
    return result.scalar() or 0


async def get_round_submissions(db: AsyncSession, debate_id: UUID, round_number: int) -> list[Turn]:
    """Get valid argument/resubmission turns for a round (excludes Phase 0 turns)."""
    result = await db.execute(
        select(Turn).where(
            Turn.debate_id == debate_id,
            Turn.round_number == round_number,
            Turn.validation_status == TurnValidationStatus.VALID,
            Turn.turn_type.in_(("argument", "resubmission")),
        )
    )
    return list(result.scalars().all())


async def check_round_complete(db: AsyncSession, debate_id: UUID) -> bool:
    """Check if all debaters have submitted valid turns for the current round."""
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        return False

    debater_count = await get_debater_count(db, debate_id)
    submissions = await get_round_submissions(db, debate_id, debate.current_round)
    unique_agents = {t.agent_id for t in submissions}

    return len(unique_agents) >= debater_count


async def advance_round(db: AsyncSession, debate_id: UUID) -> None:
    """Advance to the next round."""
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        return

    debate.current_round += 1

    if debate.current_round > debate.max_rounds:
        debate.status = DebateStatus.COMPLETED
        debate.completed_at = datetime.utcnow()
        try:
            from app.tasks.arbiter_tasks import evaluate_debate
            evaluate_debate.delay(str(debate_id))
        except Exception as e:
            logger.warning(f"Celery unavailable for evaluate_debate on {debate_id}, running inline: {e}")
            try:
                from app.tasks.arbiter_tasks import _evaluate_debate_async
                await _evaluate_debate_async(str(debate_id))
            except Exception as e2:
                logger.error(f"Inline evaluate_debate also failed for {debate_id}: {e2}")


async def process_phase0_turn(db: AsyncSession, debate_id: UUID, agent_id: UUID, turn: Turn) -> dict:
    """Process a Phase 0 turn. Returns status info."""
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        return {"error": "debate_not_found"}

    if debate.status != DebateStatus.PHASE_0:
        return {"error": "not_in_phase_0"}

    if turn.turn_type == "phase_0_declaration":
        return await _process_declaration(db, debate, agent_id, turn)
    elif turn.turn_type == "phase_0_negotiation":
        return await _process_negotiation(db, debate, agent_id, turn)

    return {"status": "processed"}


async def _process_declaration(db: AsyncSession, debate: Debate, agent_id: UUID, turn: Turn) -> dict:
    """Process a Phase 0 declaration — agent declares hard core + auxiliaries."""
    debater_count = await get_debater_count(db, debate.id)

    # Count declarations across ALL rounds (agents may have declared at different rounds)
    result = await db.execute(
        select(Turn).where(
            Turn.debate_id == debate.id,
            Turn.turn_type == "phase_0_declaration",
            Turn.validation_status == TurnValidationStatus.VALID,
        )
    )
    declarations = list(result.scalars().all())
    unique_declarers = {t.agent_id for t in declarations}

    if len(unique_declarers) >= debater_count:
        # All declared — auto-transition to ACTIVE (skip negotiation for MVP)
        logger.info(f"All {debater_count} agents declared in debate {debate.id}, auto-activating")
        await _lock_structure_and_activate(db, debate)
        return {"status": "all_declared", "debate_status": "active", "message": "All agents declared. Debate is now ACTIVE. Submit argument turns."}

    return {"status": "declaration_received", "declarations": len(unique_declarers), "needed": debater_count}


async def _process_negotiation(db: AsyncSession, debate: Debate, agent_id: UUID, turn: Turn) -> dict:
    """Process Phase 0 negotiation turn."""
    debater_count = await get_debater_count(db, debate.id)
    max_p0_rounds = debate.config.get("phase_0_max_rounds", 3)

    # Check if all agents have negotiated this round
    result = await db.execute(
        select(Turn).where(
            Turn.debate_id == debate.id,
            Turn.round_number == debate.current_round,
            Turn.turn_type == "phase_0_negotiation",
        )
    )
    negotiations = list(result.scalars().all())
    unique_negotiators = {t.agent_id for t in negotiations}

    if len(unique_negotiators) >= debater_count:
        # Check for consensus (simplified: check if turn content contains "accept")
        accepts = sum(1 for t in negotiations if "accept" in t.content.lower())
        if accepts >= debater_count:
            # Consensus reached — lock structure and transition to ACTIVE
            await _lock_structure_and_activate(db, debate)
            return {"status": "consensus_reached", "debate_status": "active"}

        # No consensus — advance round or deadlock
        if debate.current_round >= max_p0_rounds:
            return {"status": "deadlocked", "action": "arbiter_impose"}
        else:
            debate.current_round += 1
            return {"status": "round_advanced", "round": debate.current_round}

    return {"status": "negotiation_received", "negotiations": len(unique_negotiators), "needed": debater_count}


async def _lock_structure_and_activate(db: AsyncSession, debate: Debate) -> None:
    """Lock Phase 0 structure, capture pre-debate snapshots, transition to ACTIVE."""
    # Build phase_0_structure from declaration turns (more reliable than participant fields)
    result = await db.execute(
        select(DebateParticipant).where(
            DebateParticipant.debate_id == debate.id,
            DebateParticipant.role == ParticipantRole.DEBATER,
        )
    )
    participants = list(result.scalars().all())

    # Get the latest declaration turn per agent
    decl_result = await db.execute(
        select(Turn).where(
            Turn.debate_id == debate.id,
            Turn.turn_type == "phase_0_declaration",
            Turn.validation_status == TurnValidationStatus.VALID,
        ).order_by(Turn.created_at.desc())
    )
    declarations = list(decl_result.scalars().all())
    agent_declarations = {}
    for d in declarations:
        if d.agent_id not in agent_declarations:
            agent_declarations[d.agent_id] = d

    structure = {}
    for p in participants:
        decl = agent_declarations.get(p.agent_id)
        if decl:
            # Extract structure from declaration turn content
            structure[str(p.agent_id)] = {
                "hard_core": decl.content[:500],  # Use turn content as the position
                "auxiliaries": p.auxiliary_hypotheses or [],
                "declaration_turn_id": str(decl.id),
            }
        else:
            structure[str(p.agent_id)] = {
                "hard_core": p.hard_core or "",
                "auxiliaries": p.auxiliary_hypotheses or [],
            }
    structure["imposed_by_arbiter"] = False

    debate.phase_0_structure = structure
    debate.status = DebateStatus.ACTIVE
    debate.current_round = 1

    # Transition linked thesis to DEBATING
    if debate.source_thesis_id:
        thesis_result = await db.execute(
            select(Thesis).where(Thesis.id == debate.source_thesis_id)
        )
        thesis = thesis_result.scalar_one_or_none()
        if thesis and thesis.status == ThesisStatus.CHALLENGED:
            thesis.status = ThesisStatus.DEBATING

    # Capture pre-debate position snapshots
    for p in participants:
        decl = agent_declarations.get(p.agent_id)
        snapshot = PositionSnapshot(
            agent_id=p.agent_id,
            debate_id=debate.id,
            snapshot_type=SnapshotType.PRE_DEBATE,
            hard_core=decl.content[:500] if decl else (p.hard_core or ""),
            auxiliary_hypotheses=p.auxiliary_hypotheses or [],
        )
        db.add(snapshot)


async def impose_default_structure(db: AsyncSession, debate_id: UUID, structure: dict) -> None:
    """Arbiter imposes a default structure when Phase 0 deadlocks."""
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate:
        return

    structure["imposed_by_arbiter"] = True
    debate.phase_0_structure = structure
    debate.status = DebateStatus.ACTIVE
    debate.current_round = 1

    # Transition linked thesis to DEBATING
    if debate.source_thesis_id:
        thesis_result = await db.execute(
            select(Thesis).where(Thesis.id == debate.source_thesis_id)
        )
        thesis = thesis_result.scalar_one_or_none()
        if thesis and thesis.status == ThesisStatus.CHALLENGED:
            thesis.status = ThesisStatus.DEBATING

    # Capture pre-debate snapshots
    participants_result = await db.execute(
        select(DebateParticipant).where(
            DebateParticipant.debate_id == debate_id,
            DebateParticipant.role == ParticipantRole.DEBATER,
        )
    )
    for p in participants_result.scalars().all():
        agent_structure = structure.get(str(p.agent_id), {})
        snapshot = PositionSnapshot(
            agent_id=p.agent_id,
            debate_id=debate_id,
            snapshot_type=SnapshotType.PRE_DEBATE,
            hard_core=agent_structure.get("hard_core", ""),
            auxiliary_hypotheses=agent_structure.get("auxiliaries", []),
        )
        db.add(snapshot)


async def forfeit_overdue_turns(db: AsyncSession, debate_id: UUID) -> list[UUID]:
    """Skip agents who missed their turn deadline. Returns list of skipped agent IDs."""
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate or debate.status != DebateStatus.ACTIVE:
        return []

    deadline_seconds = debate.config.get("turn_deadline_seconds")
    if not deadline_seconds:
        return []

    # Get all debaters
    participants_result = await db.execute(
        select(DebateParticipant).where(
            DebateParticipant.debate_id == debate_id,
            DebateParticipant.role == ParticipantRole.DEBATER,
        )
    )
    participants = list(participants_result.scalars().all())
    all_agent_ids = {p.agent_id for p in participants}

    # Get agents who already submitted this round
    submissions_result = await db.execute(
        select(Turn.agent_id).where(
            Turn.debate_id == debate_id,
            Turn.round_number == debate.current_round,
        )
    )
    submitted = {row[0] for row in submissions_result.all()}

    # Agents who haven't submitted
    missing = all_agent_ids - submitted
    return list(missing)
