"""Core debate action logic — shared by /turns and /act endpoints."""
import logging
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import Agent
from app.models.debate import Debate, DebateParticipant, Turn
from app.models.enums import DebateStatus, ParticipantRole, TurnValidationStatus
from app.schemas.debate import ControlPlane, TurnResponse

logger = logging.getLogger(__name__)


@dataclass
class SubmitResult:
    """Result of a turn submission with round context."""
    turn: Turn
    round_advanced: bool = False
    new_round: int = 0
    debate_status: str = "active"
    debate_completed: bool = False
    opponent_turns: list = field(default_factory=list)
    phase0_result: Optional[dict] = None


async def get_opponent_turns(
    db: AsyncSession, debate_id: UUID, round_number: int, exclude_agent_id: UUID
) -> list[Turn]:
    """Get all valid turns from a round, excluding the given agent."""
    result = await db.execute(
        select(Turn).where(
            Turn.debate_id == debate_id,
            Turn.round_number == round_number,
            Turn.agent_id != exclude_agent_id,
            Turn.validation_status == TurnValidationStatus.VALID,
        ).order_by(Turn.created_at.asc())
    )
    return list(result.scalars().all())


async def get_participants_info(
    db: AsyncSession, debate_id: UUID
) -> list[dict]:
    """Get participant info for a debate."""
    result = await db.execute(
        select(DebateParticipant, Agent).join(
            Agent, Agent.id == DebateParticipant.agent_id
        ).where(
            DebateParticipant.debate_id == debate_id,
            DebateParticipant.role == ParticipantRole.DEBATER,
        )
    )
    participants = []
    for participant, agent in result.all():
        participants.append({
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "school_of_thought": participant.school_of_thought or agent.school_of_thought,
        })
    return participants


async def build_control_plane(
    db: AsyncSession, debate: Debate, agent: Agent
) -> ControlPlane:
    """Build the control plane for an agent in a debate."""
    from sqlalchemy import func as sa_func

    debate_id = debate.id

    # Count debaters
    debater_count_result = await db.execute(
        select(sa_func.count(DebateParticipant.id)).where(
            DebateParticipant.debate_id == debate_id,
            DebateParticipant.role == ParticipantRole.DEBATER,
        )
    )
    total_debaters = debater_count_result.scalar() or 0

    # Count submitted turns this round
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
    action_hint = None
    if debate.status in (DebateStatus.COMPLETED, DebateStatus.DONE, DebateStatus.EVALUATION_FAILED):
        action = "debate_complete"
    elif my_status == "rejected":
        action = "resubmit"
    elif my_status == "pending":
        action = "submit_turn"
        if debate.status == DebateStatus.PHASE_0:
            decl_result = await db.execute(
                select(Turn).where(
                    Turn.debate_id == debate_id,
                    Turn.agent_id == agent.id,
                    Turn.turn_type == "phase_0_declaration",
                    Turn.validation_status == TurnValidationStatus.VALID,
                ).limit(1)
            )
            if decl_result.scalar_one_or_none():
                action = "wait"
                action_hint = "Your Phase 0 declaration is submitted. Waiting for other agents to declare."
            else:
                action_hint = "Submit a phase_0_declaration turn with your hard core thesis, auxiliary hypotheses, and falsification criteria."
        elif debate.status == DebateStatus.ACTIVE:
            action_hint = "Submit an argument turn. Toulmin tags are optional (auto-generated if omitted)."
    else:
        action = "wait"
        if debate.status == DebateStatus.PHASE_0:
            action_hint = "Your declaration is submitted. Waiting for other agents."
        elif debate.status == DebateStatus.ACTIVE:
            action_hint = "Your turn is submitted. Waiting for other agents to complete this round."

    # Turn deadline
    turn_deadline_at = None
    deadline_seconds = debate.config.get("turn_deadline_seconds")
    if deadline_seconds and debate.status in (DebateStatus.ACTIVE, DebateStatus.PHASE_0):
        from datetime import timedelta
        last_turn_result = await db.execute(
            select(Turn.created_at).where(
                Turn.debate_id == debate_id,
                Turn.round_number == debate.current_round,
            ).order_by(Turn.created_at.desc()).limit(1)
        )
        last_turn_row = last_turn_result.one_or_none()
        if last_turn_row:
            turn_deadline_at = last_turn_row[0] + timedelta(seconds=deadline_seconds)

    return ControlPlane(
        my_submission_status=my_status,
        round_submissions={"total": total_debaters, "submitted": len(submitted_agents)},
        turn_deadline_at=turn_deadline_at,
        action_needed=action,
        action_hint=action_hint,
    )
