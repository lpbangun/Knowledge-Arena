"""Thesis board service — manages thesis lifecycle and auto-creates debates on challenge acceptance."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.agent import Agent
from app.models.debate import Debate, DebateParticipant
from app.models.enums import DebateStatus, ParticipantRole, ThesisStatus
from app.models.thesis import Thesis


async def accept_challenge(
    db: AsyncSession,
    thesis_id: UUID,
    challenger: Agent,
    max_rounds: int = 8,
    config: dict | None = None,
) -> Debate:
    """Accept a thesis challenge: creates a debate with poster + challenger auto-joined."""
    result = await db.execute(select(Thesis).where(Thesis.id == thesis_id))
    thesis = result.scalar_one_or_none()
    if not thesis:
        raise ValueError("Thesis not found")
    if thesis.status != ThesisStatus.OPEN:
        raise ValueError("Thesis is not open for challenge")
    if thesis.agent_id == challenger.id:
        raise ValueError("Cannot challenge your own thesis")
    if challenger.elo_rating < settings.MIN_ELO_ACCEPT_CHALLENGE:
        raise ValueError(f"Minimum Elo {settings.MIN_ELO_ACCEPT_CHALLENGE} required to accept challenges")

    # Create debate from thesis
    debate = Debate(
        topic=thesis.claim,
        description=f"Debate originated from thesis challenge. Challenge type: {thesis.challenge_type or 'open'}",
        category=thesis.category,
        created_by=thesis.agent_id,
        source_thesis_id=thesis.id,
        config=config or {},
        max_rounds=max_rounds,
        status=DebateStatus.PHASE_0,
    )
    db.add(debate)
    await db.flush()

    # Auto-join poster as debater
    poster_participant = DebateParticipant(
        debate_id=debate.id,
        agent_id=thesis.agent_id,
        role=ParticipantRole.DEBATER,
        citation_challenges_remaining=settings.DEFAULT_CITATION_CHALLENGES_DEBATER,
    )
    db.add(poster_participant)

    # Auto-join challenger as debater
    challenger_participant = DebateParticipant(
        debate_id=debate.id,
        agent_id=challenger.id,
        role=ParticipantRole.DEBATER,
        citation_challenges_remaining=settings.DEFAULT_CITATION_CHALLENGES_DEBATER,
    )
    db.add(challenger_participant)

    # Update thesis status
    thesis.status = ThesisStatus.CHALLENGED
    thesis.challenger_count += 1

    await db.flush()
    return debate


async def get_categories(db: AsyncSession) -> list[str]:
    """Get distinct thesis categories."""
    result = await db.execute(
        select(Thesis.category)
        .where(Thesis.category.isnot(None))
        .distinct()
    )
    return [row[0] for row in result.all()]
