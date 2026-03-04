from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debate import Debate, Turn
from app.models.enums import DebateStatus, TurnValidationStatus


async def check_convergence(db: AsyncSession, debate_id: UUID) -> bool:
    """
    Check if a debate should end early due to convergence.
    Three signals must all be present:
    1. Repetition: >60% semantic overlap with previous turns (simplified: text similarity)
    2. Concession rate: increasing over last 3 rounds
    3. No new challenges: 2+ rounds without new falsification targets
    """
    result = await db.execute(select(Debate).where(Debate.id == debate_id))
    debate = result.scalar_one_or_none()
    if not debate or debate.status != DebateStatus.ACTIVE:
        return False

    if debate.current_round < 3:
        return False

    # Get all valid turns
    turns_result = await db.execute(
        select(Turn).where(
            Turn.debate_id == debate_id,
            Turn.validation_status == TurnValidationStatus.VALID,
        ).order_by(Turn.round_number, Turn.created_at)
    )
    turns = list(turns_result.scalars().all())

    if len(turns) < 4:
        return False

    # Signal 1: Repetition detection (simplified — check word overlap)
    repetition = _check_repetition(turns)

    # Signal 2: Concession rate increasing
    concession_increasing = _check_concession_rate(turns)

    # Signal 3: No new challenges for 2+ rounds
    no_new_challenges = _check_no_new_challenges(turns, debate.current_round)

    signals = {
        "repetition_detected": repetition,
        "concession_rate_increasing": concession_increasing,
        "no_new_challenges_rounds": _rounds_without_challenges(turns, debate.current_round),
    }
    debate.convergence_signals = signals

    all_converged = repetition and concession_increasing and no_new_challenges
    if all_converged and debate.status == DebateStatus.ACTIVE:
        debate.status = DebateStatus.CONVERGED
        try:
            from app.tasks.arbiter_tasks import evaluate_debate
            evaluate_debate.delay(str(debate_id))
        except Exception as e:
            import asyncio
            import logging
            _logger = logging.getLogger(__name__)
            _logger.warning(f"Celery unavailable for evaluate_debate on {debate_id}, falling back to inline: {e}")
            try:
                from app.tasks.arbiter_tasks import _evaluate_debate_async
                asyncio.ensure_future(_evaluate_debate_async(str(debate_id)))
            except Exception as e2:
                _logger.error(f"Inline evaluate_debate fallback also failed for {debate_id}: {e2}")

    return all_converged


def _check_repetition(turns: list[Turn]) -> bool:
    """Simplified repetition detection: check if recent turns share >60% words with earlier turns."""
    if len(turns) < 4:
        return False

    recent = turns[-2:]
    earlier = turns[:-2]

    for recent_turn in recent:
        recent_words = set(recent_turn.content.lower().split())
        for earlier_turn in earlier:
            if recent_turn.agent_id == earlier_turn.agent_id:
                earlier_words = set(earlier_turn.content.lower().split())
                if recent_words and earlier_words:
                    overlap = len(recent_words & earlier_words) / max(len(recent_words), 1)
                    if overlap > 0.6:
                        return True
    return False


def _check_concession_rate(turns: list[Turn]) -> bool:
    """Check if concession-related language is increasing."""
    concession_words = {"concede", "agree", "accept", "acknowledge", "grant", "fair point", "valid point"}

    rounds = {}
    for turn in turns:
        r = turn.round_number
        if r not in rounds:
            rounds[r] = 0
        content_lower = turn.content.lower()
        for word in concession_words:
            if word in content_lower:
                rounds[r] += 1

    sorted_rounds = sorted(rounds.keys())
    if len(sorted_rounds) < 3:
        return False

    last_three = sorted_rounds[-3:]
    rates = [rounds[r] for r in last_three]
    return rates[-1] >= rates[-2] >= rates[-3] and rates[-1] > 0


def _check_no_new_challenges(turns: list[Turn], current_round: int) -> bool:
    return _rounds_without_challenges(turns, current_round) >= 2


def _rounds_without_challenges(turns: list[Turn], current_round: int) -> int:
    """Count consecutive rounds without new falsification targets."""
    count = 0
    for r in range(current_round, 0, -1):
        round_turns = [t for t in turns if t.round_number == r]
        has_challenge = any(t.falsification_target for t in round_turns)
        if has_challenge:
            break
        count += 1
    return count
