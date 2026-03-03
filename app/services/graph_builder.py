from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.graph import GraphEdge, GraphNode
from app.models.enums import GraphEdgeType, GraphNodeType, VerificationStatus


NODE_TYPE_MAP = {
    "claim": GraphNodeType.EMPIRICAL_CLAIM,
    "evidence": GraphNodeType.EVIDENCE,
    "position": GraphNodeType.SYNTHESIS_POSITION,
    "methodology": GraphNodeType.EMPIRICAL_CLAIM,
    "hard_core": GraphNodeType.HARD_CORE,
    "auxiliary_hypothesis": GraphNodeType.AUXILIARY_HYPOTHESIS,
    "open_question": GraphNodeType.OPEN_QUESTION,
}

EDGE_TYPE_MAP = {
    "supports": GraphEdgeType.SUPPORTS,
    "contradicts": GraphEdgeType.CONTRADICTS,
    "refines": GraphEdgeType.EXTENDS,
    "extends": GraphEdgeType.EXTENDS,
    "falsifies": GraphEdgeType.FALSIFIES,
    "qualifies": GraphEdgeType.QUALIFIES,
    "synthesizes": GraphEdgeType.SYNTHESIZES,
    "challenges": GraphEdgeType.CHALLENGES,
}


async def process_graph_updates(db: AsyncSession, debate_id: UUID, graph_updates: dict) -> dict:
    """Process graph update instructions from Layer 2 evaluation."""
    created_nodes = []
    created_edges = []

    # Process new nodes
    for node_data in graph_updates.get("new_nodes", []):
        node_type = NODE_TYPE_MAP.get(node_data.get("node_type", "claim"), GraphNodeType.EMPIRICAL_CLAIM)
        source_agent_id = None
        if node_data.get("source_agent_id"):
            try:
                source_agent_id = UUID(node_data["source_agent_id"])
            except (ValueError, TypeError):
                pass

        node = GraphNode(
            node_type=node_type,
            content=node_data.get("content", ""),
            source_debate_id=debate_id,
            source_agent_id=source_agent_id,
            toulmin_category=node_data.get("toulmin_category"),
            quality_score=node_data.get("suggested_quality_score"),
            verification_status=VerificationStatus.UNVERIFIED,
        )
        db.add(node)
        await db.flush()
        created_nodes.append({"id": str(node.id), "content": node.content})

    # Process new edges
    node_cache = {}
    for edge_data in graph_updates.get("new_edges", []):
        source_content = edge_data.get("source_content", "")
        target_content = edge_data.get("target_content", "")
        edge_type = EDGE_TYPE_MAP.get(edge_data.get("edge_type", "supports"), GraphEdgeType.SUPPORTS)

        source_node = await _find_or_create_node(db, debate_id, source_content, node_cache)
        target_node = await _find_or_create_node(db, debate_id, target_content, node_cache)

        if source_node and target_node:
            edge = GraphEdge(
                source_node_id=source_node.id,
                target_node_id=target_node.id,
                edge_type=edge_type,
                source_debate_id=debate_id,
                strength=edge_data.get("strength", 0.5),
            )
            db.add(edge)
            created_edges.append({
                "source": source_content[:50],
                "target": target_content[:50],
                "type": edge_type.value,
            })

    # Process node updates
    for update_data in graph_updates.get("update_nodes", []):
        node_id = update_data.get("node_id")
        updates = update_data.get("updates", {})
        if node_id:
            try:
                result = await db.execute(select(GraphNode).where(GraphNode.id == UUID(node_id)))
                node = result.scalar_one_or_none()
                if node:
                    if "status" in updates:
                        status_map = {
                            "falsified": VerificationStatus.FALSIFIED,
                            "verified": VerificationStatus.VERIFIED,
                            "challenged": VerificationStatus.CHALLENGED,
                        }
                        node.verification_status = status_map.get(updates["status"], node.verification_status)
                    if "quality_score" in updates:
                        node.quality_score = updates["quality_score"]
            except (ValueError, TypeError):
                pass

    return {"nodes_created": len(created_nodes), "edges_created": len(created_edges)}


async def _find_or_create_node(
    db: AsyncSession, debate_id: UUID, content: str, cache: dict
) -> Optional[GraphNode]:
    """Find an existing node by content or create a new one."""
    if content in cache:
        return cache[content]

    # Search for existing node with similar content
    result = await db.execute(
        select(GraphNode).where(GraphNode.content == content).limit(1)
    )
    node = result.scalar_one_or_none()

    if not node:
        node = GraphNode(
            node_type=GraphNodeType.EMPIRICAL_CLAIM,
            content=content,
            source_debate_id=debate_id,
        )
        db.add(node)
        await db.flush()

    cache[content] = node
    return node
