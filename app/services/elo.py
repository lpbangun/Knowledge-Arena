import math
from typing import Optional
from uuid import UUID

from app.models.evaluation import DebateEvaluation


K_PROVISIONAL = 32  # < 20 debates
K_ESTABLISHED = 16  # >= 20 debates
ELO_FLOOR = 100


def get_k_factor(total_debates: int) -> int:
    return K_PROVISIONAL if total_debates < 20 else K_ESTABLISHED


def expected_score(rating_a: int, rating_b: int) -> float:
    return 1.0 / (1.0 + math.pow(10, (rating_b - rating_a) / 400.0))


def actual_score(composite_a: float, composite_b: float) -> float:
    if composite_a > composite_b:
        return 1.0
    elif composite_a == composite_b:
        return 0.5
    return 0.0


def calculate_elo_adjustments(
    evaluations: list[dict],
    current_ratings: dict[str, int],
    total_debates: dict[str, int],
    audience_votes: Optional[dict[str, float]] = None,
    bonuses: Optional[dict[str, int]] = None,
) -> dict[str, int]:
    """
    Calculate Elo adjustments for all debaters.

    evaluations: list of {"agent_id": str, "composite_score": float}
    current_ratings: {agent_id: current_elo}
    total_debates: {agent_id: debate_count}
    audience_votes: {agent_id: avg_audience_score} (optional)
    bonuses: {agent_id: bonus_points} (optional, e.g., citation challenges, diversity)

    Returns: {agent_id: new_elo_rating}
    """
    agent_ids = [e["agent_id"] for e in evaluations]
    scores = {e["agent_id"]: e["composite_score"] for e in evaluations}

    if len(agent_ids) < 2:
        return {aid: current_ratings.get(aid, 1000) for aid in agent_ids}

    # Step 1: Pairwise Elo deltas
    raw_deltas: dict[str, float] = {aid: 0.0 for aid in agent_ids}

    for i, a_id in enumerate(agent_ids):
        pair_deltas = []
        k = get_k_factor(total_debates.get(a_id, 0))

        for j, b_id in enumerate(agent_ids):
            if i == j:
                continue

            e_a = expected_score(current_ratings.get(a_id, 1000), current_ratings.get(b_id, 1000))
            s_a = actual_score(scores[a_id], scores[b_id])
            delta = k * (s_a - e_a)
            pair_deltas.append(delta)

        raw_deltas[a_id] = sum(pair_deltas) / len(pair_deltas) if pair_deltas else 0.0

    # Step 2: Audience modifier (20% pull toward audience consensus)
    if audience_votes:
        arbiter_ranking = sorted(agent_ids, key=lambda x: scores[x], reverse=True)
        audience_ranking = sorted(
            [a for a in agent_ids if a in audience_votes],
            key=lambda x: audience_votes[x],
            reverse=True,
        )

        if arbiter_ranking != audience_ranking and len(audience_ranking) >= 2:
            # Compute audience-implied deltas
            audience_scores = {aid: audience_votes.get(aid, 0.0) for aid in agent_ids}
            audience_deltas: dict[str, float] = {aid: 0.0 for aid in agent_ids}

            for i, a_id in enumerate(agent_ids):
                pair_deltas = []
                k = get_k_factor(total_debates.get(a_id, 0))
                for j, b_id in enumerate(agent_ids):
                    if i == j:
                        continue
                    e_a = expected_score(current_ratings.get(a_id, 1000), current_ratings.get(b_id, 1000))
                    s_a = actual_score(audience_scores.get(a_id, 0.5), audience_scores.get(b_id, 0.5))
                    delta = k * (s_a - e_a)
                    pair_deltas.append(delta)
                audience_deltas[a_id] = sum(pair_deltas) / len(pair_deltas) if pair_deltas else 0.0

            # Pull 20% toward audience
            for aid in agent_ids:
                raw_deltas[aid] = 0.8 * raw_deltas[aid] + 0.2 * audience_deltas.get(aid, 0.0)

    # Step 3: Apply bonuses
    if bonuses:
        for aid, bonus in bonuses.items():
            if aid in raw_deltas:
                raw_deltas[aid] += bonus

    # Step 4: Compute new ratings with floor
    new_ratings = {}
    for aid in agent_ids:
        new_elo = current_ratings.get(aid, 1000) + round(raw_deltas[aid])
        new_ratings[aid] = max(new_elo, ELO_FLOOR)

    return new_ratings
