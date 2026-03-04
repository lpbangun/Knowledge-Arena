from sqlalchemy import select, func
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
    """Find empirical claims with SUPPORTS edges but no CONTRADICTS edges.
    Uses a single aggregated query instead of per-node queries.
    """
    # Get candidate nodes
    result = await db.execute(
        select(GraphNode).where(
            GraphNode.node_type == GraphNodeType.EMPIRICAL_CLAIM,
        ).limit(50)
    )
    nodes = list(result.scalars().all())
    if not nodes:
        return []

    node_ids = [n.id for n in nodes]

    # Single query: aggregate edge types per target node
    edge_counts = await db.execute(
        select(
            GraphEdge.target_node_id,
            func.bool_or(GraphEdge.edge_type == GraphEdgeType.SUPPORTS).label("has_supports"),
            func.bool_or(GraphEdge.edge_type == GraphEdgeType.CONTRADICTS).label("has_contradicts"),
        )
        .where(GraphEdge.target_node_id.in_(node_ids))
        .group_by(GraphEdge.target_node_id)
    )
    edge_rows = {row[0]: (row[1], row[2]) for row in edge_counts.all()}

    one_sided = []
    for node in nodes:
        info = edge_rows.get(node.id)
        if info and info[0] and not info[1]:  # has_supports=True, has_contradicts=False
            one_sided.append(node)
            if len(one_sided) >= 10:
                break

    return one_sided


async def _find_contradictory_syntheses(db: AsyncSession) -> list[dict]:
    """Find synthesis nodes that share evidence but reach different conclusions.
    Uses batch-loaded edges instead of per-pair queries.
    """
    result = await db.execute(
        select(GraphNode).where(
            GraphNode.node_type == GraphNodeType.SYNTHESIS_POSITION,
        ).limit(20)
    )
    syntheses = list(result.scalars().all())
    if not syntheses:
        return []

    synthesis_ids = [s.id for s in syntheses]

    # Single query: load all SUPPORTS edges targeting any synthesis node
    edges_result = await db.execute(
        select(GraphEdge.target_node_id, GraphEdge.source_node_id).where(
            GraphEdge.target_node_id.in_(synthesis_ids),
            GraphEdge.edge_type == GraphEdgeType.SUPPORTS,
        )
    )

    # Build source-set per synthesis node
    sources_by_node: dict = {}
    for row in edges_result.all():
        target_id, source_id = row[0], row[1]
        if target_id not in sources_by_node:
            sources_by_node[target_id] = set()
        sources_by_node[target_id].add(source_id)

    # Check pairwise overlap in Python
    gaps = []
    for i, s1 in enumerate(syntheses):
        s1_sources = sources_by_node.get(s1.id, set())
        if not s1_sources:
            continue
        for s2 in syntheses[i + 1:]:
            s2_sources = sources_by_node.get(s2.id, set())
            shared = s1_sources & s2_sources
            if shared:
                gaps.append({
                    "type": "contradictory_syntheses",
                    "node_ids": [str(s1.id), str(s2.id)],
                    "shared_evidence_count": len(shared),
                    "content_a": s1.content[:100],
                    "content_b": s2.content[:100],
                    "suggested_framing": "Resolve contradicting syntheses with shared evidence",
                })

    return gaps
