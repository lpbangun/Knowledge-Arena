from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import BeliefUpdatePacket, PositionSnapshot
from app.models.enums import SnapshotType


async def get_evolution_timeline(db: AsyncSession, agent_id: UUID) -> list[dict]:
    """Get chronological position snapshots with diffs."""
    result = await db.execute(
        select(PositionSnapshot)
        .where(PositionSnapshot.agent_id == agent_id)
        .order_by(PositionSnapshot.created_at.asc())
    )
    snapshots = list(result.scalars().all())

    timeline = []
    prev = None
    for snap in snapshots:
        entry = {
            "id": str(snap.id),
            "debate_id": str(snap.debate_id) if snap.debate_id else None,
            "bup_id": str(snap.bup_id) if snap.bup_id else None,
            "snapshot_type": snap.snapshot_type.value,
            "hard_core": snap.hard_core,
            "auxiliary_hypotheses": snap.auxiliary_hypotheses,
            "qualifier_count": snap.qualifier_count,
            "created_at": snap.created_at.isoformat(),
            "diff": None,
        }

        if prev:
            entry["diff"] = compute_diff(prev, snap)

        timeline.append(entry)
        prev = snap

    return timeline


def compute_diff(prev: PositionSnapshot, current: PositionSnapshot) -> dict:
    """Compute diff between two position snapshots."""
    diff = {
        "hard_core_changed": prev.hard_core != current.hard_core,
        "auxiliaries_added": [],
        "auxiliaries_removed": [],
        "auxiliaries_modified": [],
    }

    prev_aux = {a.get("hypothesis", ""): a for a in (prev.auxiliary_hypotheses or [])}
    curr_aux = {a.get("hypothesis", ""): a for a in (current.auxiliary_hypotheses or [])}

    prev_keys = set(prev_aux.keys())
    curr_keys = set(curr_aux.keys())

    diff["auxiliaries_added"] = list(curr_keys - prev_keys)
    diff["auxiliaries_removed"] = list(prev_keys - curr_keys)

    for key in prev_keys & curr_keys:
        if prev_aux[key] != curr_aux[key]:
            diff["auxiliaries_modified"].append(key)

    return diff


async def get_learnings(db: AsyncSession, agent_id: UUID, limit: int = 50) -> list[dict]:
    """Get all BUPs for an agent."""
    result = await db.execute(
        select(BeliefUpdatePacket)
        .where(BeliefUpdatePacket.agent_id == agent_id)
        .order_by(BeliefUpdatePacket.created_at.desc())
        .limit(limit)
    )
    bups = list(result.scalars().all())

    return [{
        "id": str(b.id),
        "debate_id": str(b.debate_id),
        "concessions_made": b.concessions_made,
        "concessions_resisted": b.concessions_resisted,
        "new_evidence": b.new_evidence,
        "strongest_counterarguments": b.strongest_counterarguments,
        "synthesis_insights": b.synthesis_insights,
        "recommended_updates": b.recommended_updates,
        "falsification_outcomes": b.falsification_outcomes,
        "created_at": b.created_at.isoformat(),
    } for b in bups]


async def get_latest_learning(db: AsyncSession, agent_id: UUID) -> dict | None:
    """Get the most recent BUP."""
    result = await db.execute(
        select(BeliefUpdatePacket)
        .where(BeliefUpdatePacket.agent_id == agent_id)
        .order_by(BeliefUpdatePacket.created_at.desc())
        .limit(1)
    )
    bup = result.scalar_one_or_none()
    if not bup:
        return None

    return {
        "id": str(bup.id),
        "debate_id": str(bup.debate_id),
        "concessions_made": bup.concessions_made,
        "concessions_resisted": bup.concessions_resisted,
        "new_evidence": bup.new_evidence,
        "strongest_counterarguments": bup.strongest_counterarguments,
        "synthesis_insights": bup.synthesis_insights,
        "recommended_updates": bup.recommended_updates,
        "falsification_outcomes": bup.falsification_outcomes,
        "created_at": bup.created_at.isoformat(),
    }


async def get_learning_summary(db: AsyncSession, agent_id: UUID) -> dict:
    """Aggregated learning summary across all BUPs."""
    result = await db.execute(
        select(BeliefUpdatePacket)
        .where(BeliefUpdatePacket.agent_id == agent_id)
        .order_by(BeliefUpdatePacket.created_at.desc())
    )
    bups = list(result.scalars().all())

    total_concessions_made = sum(len(b.concessions_made) for b in bups)
    total_concessions_resisted = sum(len(b.concessions_resisted) for b in bups)
    total_new_evidence = sum(len(b.new_evidence) for b in bups)
    total_debates = len(bups)

    falsification_survived = 0
    falsification_total = 0
    for b in bups:
        for f in b.falsification_outcomes:
            falsification_total += 1
            if f.get("outcome") == "survived":
                falsification_survived += 1

    return {
        "total_debates": total_debates,
        "total_concessions_made": total_concessions_made,
        "total_concessions_resisted": total_concessions_resisted,
        "total_new_evidence_items": total_new_evidence,
        "resilience_score": falsification_survived / max(falsification_total, 1),
        "falsification_attempts_faced": falsification_total,
        "falsification_survived": falsification_survived,
    }
