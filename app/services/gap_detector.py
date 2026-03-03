from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEdge, GraphNode
from app.models.enums import GraphEdgeType, GraphNodeType


async def find_gaps(db: AsyncSession) -> list[dict]:
    """Find knowledge graph gaps using 3 heuristic queries."""
    gaps = []

    # 1. Unchallenged auxiliaries: nodes with zero incoming CHALLENGES or FALSIFIES edges
    unchallenged = await _find_unchallenged_auxiliaries(db)
    for node in unchallenged:
        gaps.append({
            "type": "unchallenged_auxiliary",
            "node_id": str(node.id),
            "content": node.content,
            "suggested_framing": f"Challenge the hypothesis: {node.content[:100]}...",
        })

    # 2. One-sided evidence: claims with SUPPORTS but no CONTRADICTS
    one_sided = await _find_one_sided_evidence(db)
    for node in one_sided:
        gaps.append({
            "type": "one_sided_evidence",
            "node_id": str(node.id),
            "content": node.content,
            "suggested_framing": f"Find counter-evidence for: {node.content[:100]}...",
        })

    # 3. Contradictory syntheses sharing evidence
    contradictory = await _find_contradictory_syntheses(db)
    gaps.extend(contradictory)

    return gaps


async def _find_unchallenged_auxiliaries(db: AsyncSession) -> list[GraphNode]:
    result = await db.execute(
        select(GraphNode).where(
            GraphNode.node_type == GraphNodeType.AUXILIARY_HYPOTHESIS,
            GraphNode.challenge_count == 0,
        ).limit(20)
    )
    return list(result.scalars().all())


async def _find_one_sided_evidence(db: AsyncSession) -> list[GraphNode]:
    # Nodes with supports but no contradicts
    result = await db.execute(
        select(GraphNode).where(
            GraphNode.node_type == GraphNodeType.EMPIRICAL_CLAIM,
        ).limit(50)
    )
    nodes = list(result.scalars().all())

    one_sided = []
    for node in nodes:
        supports = await db.execute(
            select(GraphEdge).where(
                GraphEdge.target_node_id == node.id,
                GraphEdge.edge_type == GraphEdgeType.SUPPORTS,
            ).limit(1)
        )
        has_supports = supports.scalar_one_or_none() is not None

        contradicts = await db.execute(
            select(GraphEdge).where(
                GraphEdge.target_node_id == node.id,
                GraphEdge.edge_type == GraphEdgeType.CONTRADICTS,
            ).limit(1)
        )
        has_contradicts = contradicts.scalar_one_or_none() is not None

        if has_supports and not has_contradicts:
            one_sided.append(node)
            if len(one_sided) >= 10:
                break

    return one_sided


async def _find_contradictory_syntheses(db: AsyncSession) -> list[dict]:
    """Find synthesis nodes that share evidence but reach different conclusions."""
    result = await db.execute(
        select(GraphNode).where(
            GraphNode.node_type == GraphNodeType.SYNTHESIS_POSITION,
        ).limit(20)
    )
    syntheses = list(result.scalars().all())

    gaps = []
    for i, s1 in enumerate(syntheses):
        for s2 in syntheses[i + 1:]:
            # Check if they share any evidence via edges
            s1_sources = await db.execute(
                select(GraphEdge.source_node_id).where(
                    GraphEdge.target_node_id == s1.id,
                    GraphEdge.edge_type == GraphEdgeType.SUPPORTS,
                )
            )
            s2_sources = await db.execute(
                select(GraphEdge.source_node_id).where(
                    GraphEdge.target_node_id == s2.id,
                    GraphEdge.edge_type == GraphEdgeType.SUPPORTS,
                )
            )

            s1_ids = {row[0] for row in s1_sources.all()}
            s2_ids = {row[0] for row in s2_sources.all()}

            shared = s1_ids & s2_ids
            if shared:
                gaps.append({
                    "type": "contradictory_syntheses",
                    "node_ids": [str(s1.id), str(s2.id)],
                    "shared_evidence_count": len(shared),
                    "content_a": s1.content[:100],
                    "content_b": s2.content[:100],
                    "suggested_framing": f"Resolve contradicting syntheses with shared evidence",
                })

    return gaps
