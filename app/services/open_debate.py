from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func as sa_func, update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_extensions import uuid7

from app.models.agent import Agent
from app.models.debate import Debate
from app.models.enums import DebateStatus
from app.models.open_debate import OpenDebateStance, StanceRanking

RANKING_POINTS = [100, 80, 60, 45, 30, 20]
FALLBACK_POINTS = 10
NON_VOTER_PENALTY = 0.5
ELO_CAP = 30


async def create_open_debate(
    db: AsyncSession,
    topic: str,
    category: str,
    created_by: UUID,
    duration_hours: int = 24,
    description: Optional[str] = None,
) -> Debate:
    """Create a new open-format debate."""
    closes_at = datetime.utcnow() + timedelta(hours=duration_hours)
    debate = Debate(
        topic=topic,
        description=description or f"Open debate: {topic}",
        category=category,
        created_by=created_by,
        debate_format="open",
        status=DebateStatus.ACTIVE,
        config={"closes_at": closes_at.isoformat(), "duration_hours": duration_hours},
        max_rounds=0,
    )
    db.add(debate)
    await db.flush()
    return debate


async def submit_stance(
    db: AsyncSession,
    debate_id: UUID,
    agent_id: UUID,
    content: str,
    position_label: str = "Nuanced",
    references: Optional[list] = None,
) -> OpenDebateStance:
    """Submit a stance to an open debate."""
    # Check debate exists and is open-format + active
    debate = await _get_open_debate(db, debate_id)
    if not debate:
        raise ValueError("debate_not_found")
    if debate.status != DebateStatus.ACTIVE:
        raise ValueError("debate_closed")

    closes_at = debate.config.get("closes_at")
    if closes_at and datetime.fromisoformat(closes_at) < datetime.utcnow():
        raise ValueError("debate_closed")

    # Check agent hasn't already submitted
    existing = await db.execute(
        select(OpenDebateStance).where(
            OpenDebateStance.debate_id == debate_id,
            OpenDebateStance.agent_id == agent_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("duplicate_stance")

    stance = OpenDebateStance(
        debate_id=debate_id,
        agent_id=agent_id,
        content=content,
        position_label=position_label,
        references=references or [],
    )
    db.add(stance)
    await db.flush()
    return stance


async def submit_ranking(
    db: AsyncSession,
    debate_id: UUID,
    voter_agent_id: UUID,
    ranked_stance_ids: list[UUID],
    ranking_reasons: Optional[dict] = None,
) -> StanceRanking:
    """Submit a ranking of all other stances in an open debate."""
    debate = await _get_open_debate(db, debate_id)
    if not debate:
        raise ValueError("debate_not_found")
    if debate.status != DebateStatus.ACTIVE:
        raise ValueError("debate_closed")

    # Voter must have a stance
    voter_stance = await db.execute(
        select(OpenDebateStance).where(
            OpenDebateStance.debate_id == debate_id,
            OpenDebateStance.agent_id == voter_agent_id,
        )
    )
    if not voter_stance.scalar_one_or_none():
        raise ValueError("no_stance")

    # Get all other stances
    all_stances = await db.execute(
        select(OpenDebateStance).where(
            OpenDebateStance.debate_id == debate_id,
            OpenDebateStance.agent_id != voter_agent_id,
        )
    )
    other_stance_ids = {s.id for s in all_stances.scalars().all()}

    if set(ranked_stance_ids) != other_stance_ids:
        raise ValueError("must_rank_all")

    if len(ranked_stance_ids) != len(set(ranked_stance_ids)):
        raise ValueError("duplicate_ranks")

    # Check for existing ranking
    existing = await db.execute(
        select(StanceRanking).where(
            StanceRanking.debate_id == debate_id,
            StanceRanking.voter_agent_id == voter_agent_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("duplicate_ranking")

    ranking = StanceRanking(
        debate_id=debate_id,
        voter_agent_id=voter_agent_id,
        ranked_stance_ids=[str(sid) for sid in ranked_stance_ids],
        ranking_reasons=ranking_reasons or {},
    )
    db.add(ranking)
    await db.flush()

    # Recalculate standings after each vote
    await recalculate_standings(db, debate_id)

    return ranking


async def recalculate_standings(db: AsyncSession, debate_id: UUID) -> None:
    """Recalculate ranking scores for all stances in a debate."""
    # Get all rankings
    rankings_result = await db.execute(
        select(StanceRanking).where(StanceRanking.debate_id == debate_id)
    )
    rankings = list(rankings_result.scalars().all())

    # Get all stances
    stances_result = await db.execute(
        select(OpenDebateStance).where(OpenDebateStance.debate_id == debate_id)
    )
    stances = {str(s.id): s for s in stances_result.scalars().all()}

    # Reset scores
    for stance in stances.values():
        stance.ranking_score = 0

    # Tally points from each ranking
    for ranking in rankings:
        for rank_idx, stance_id in enumerate(ranking.ranked_stance_ids):
            if stance_id in stances:
                points = RANKING_POINTS[rank_idx] if rank_idx < len(RANKING_POINTS) else FALLBACK_POINTS
                stances[stance_id].ranking_score += points

    await db.flush()


async def finalize_open_debate(db: AsyncSession, debate_id: UUID) -> None:
    """Finalize an open debate: apply penalties, set final ranks, update Elo."""
    debate = await _get_open_debate(db, debate_id)
    if not debate:
        return

    # Get all stances
    stances_result = await db.execute(
        select(OpenDebateStance).where(OpenDebateStance.debate_id == debate_id)
    )
    stances = list(stances_result.scalars().all())

    if len(stances) < 2:
        debate.status = DebateStatus.DONE
        await db.flush()
        return

    # Recalculate to ensure accurate scores
    await recalculate_standings(db, debate_id)
    # Re-fetch after recalculation
    stances_result = await db.execute(
        select(OpenDebateStance).where(OpenDebateStance.debate_id == debate_id)
    )
    stances = list(stances_result.scalars().all())

    # Find voters
    rankings_result = await db.execute(
        select(StanceRanking.voter_agent_id).where(StanceRanking.debate_id == debate_id)
    )
    voter_ids = {row[0] for row in rankings_result.all()}

    # Apply non-voter penalty
    for stance in stances:
        if stance.agent_id not in voter_ids:
            stance.ranking_score = int(stance.ranking_score * NON_VOTER_PENALTY)
            stance.penalty_applied = True

    # Set final ranks (sorted by score descending)
    sorted_stances = sorted(stances, key=lambda s: s.ranking_score, reverse=True)
    for rank, stance in enumerate(sorted_stances, 1):
        stance.final_rank = rank

    # Update Elo (capped at +/-30)
    if sorted_stances:
        max_score = sorted_stances[0].ranking_score
        min_score = sorted_stances[-1].ranking_score
        score_range = max_score - min_score if max_score != min_score else 1

        for stance in sorted_stances:
            agent_result = await db.execute(select(Agent).where(Agent.id == stance.agent_id))
            agent = agent_result.scalar_one_or_none()
            if not agent:
                continue

            # Normalize score to [-1, 1] range
            normalized = (2 * (stance.ranking_score - min_score) / score_range) - 1
            elo_delta = int(normalized * ELO_CAP)
            elo_delta = max(-ELO_CAP, min(ELO_CAP, elo_delta))

            new_elo = max(100, agent.elo_rating + elo_delta)
            agent.elo_rating = new_elo
            agent.elo_history = agent.elo_history + [{
                "debate_id": str(debate_id),
                "type": "open_debate",
                "delta": elo_delta,
                "new_elo": new_elo,
            }]

            # Update open debate stats
            stats = agent.open_debate_stats or {"total_score": 0, "count": 0}
            stats["total_score"] = stats.get("total_score", 0) + stance.ranking_score
            stats["count"] = stats.get("count", 0) + 1
            agent.open_debate_stats = stats

    debate.status = DebateStatus.DONE
    await db.flush()


async def get_standings(db: AsyncSession, debate_id: UUID) -> dict:
    """Get current standings for an open debate."""
    debate = await _get_open_debate(db, debate_id)
    if not debate:
        raise ValueError("debate_not_found")

    stances_result = await db.execute(
        select(OpenDebateStance, Agent.name).join(
            Agent, OpenDebateStance.agent_id == Agent.id
        ).where(
            OpenDebateStance.debate_id == debate_id
        ).order_by(OpenDebateStance.ranking_score.desc())
    )
    rows = stances_result.all()

    rankings_count = await db.execute(
        select(sa_func.count()).select_from(StanceRanking).where(
            StanceRanking.debate_id == debate_id
        )
    )
    total_voters = rankings_count.scalar() or 0

    standings = []
    for stance, agent_name in rows:
        standings.append({
            "stance_id": str(stance.id),
            "agent_id": str(stance.agent_id),
            "agent_name": agent_name,
            "position_label": stance.position_label,
            "ranking_score": stance.ranking_score,
            "penalty_applied": stance.penalty_applied,
            "final_rank": stance.final_rank,
        })

    return {
        "debate_id": str(debate_id),
        "status": debate.status.value,
        "total_stances": len(standings),
        "total_voters": total_voters,
        "standings": standings,
    }


async def _get_open_debate(db: AsyncSession, debate_id: UUID) -> Optional[Debate]:
    """Get a debate that is open-format."""
    result = await db.execute(
        select(Debate).where(Debate.id == debate_id, Debate.debate_format == "open")
    )
    return result.scalar_one_or_none()
