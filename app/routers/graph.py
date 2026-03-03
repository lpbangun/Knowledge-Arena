from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.graph import GraphEdge, GraphNode
from app.models.enums import GraphEdgeType, GraphNodeType, VerificationStatus
from app.schemas.common import CursorPage
from app.utils.pagination import decode_cursor, encode_cursor

router = APIRouter(prefix="/api/v1/graph", tags=["graph"])


@router.get("/nodes")
async def list_nodes(
    node_type: Optional[str] = None,
    verification: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(GraphNode).order_by(GraphNode.created_at.desc())

    if node_type:
        query = query.where(GraphNode.node_type == node_type)
    if verification:
        query = query.where(GraphNode.verification_status == verification)
    if cursor:
        cursor_id = decode_cursor(cursor)
        cursor_node = await db.execute(select(GraphNode).where(GraphNode.id == cursor_id))
        cn = cursor_node.scalar_one_or_none()
        if cn:
            query = query.where(GraphNode.created_at < cn.created_at)

    result = await db.execute(query.limit(limit + 1))
    nodes = list(result.scalars().all())
    has_more = len(nodes) > limit
    items = nodes[:limit]
    next_cursor = encode_cursor(items[-1].id) if has_more and items else None

    return {
        "items": [{
            "id": str(n.id),
            "node_type": n.node_type.value,
            "content": n.content,
            "verification_status": n.verification_status.value,
            "quality_score": n.quality_score,
            "challenge_count": n.challenge_count,
            "created_at": n.created_at.isoformat(),
        } for n in items],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


@router.get("/nodes/{node_id}")
async def get_node(node_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GraphNode).where(GraphNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail={"error": "node_not_found", "message": f"Node {node_id} does not exist"})

    # Get edges
    edges_result = await db.execute(
        select(GraphEdge).where(
            (GraphEdge.source_node_id == node_id) | (GraphEdge.target_node_id == node_id)
        )
    )
    edges = list(edges_result.scalars().all())

    return {
        "id": str(node.id),
        "node_type": node.node_type.value,
        "content": node.content,
        "verification_status": node.verification_status.value,
        "quality_score": node.quality_score,
        "challenge_count": node.challenge_count,
        "created_at": node.created_at.isoformat(),
        "edges": [{
            "id": str(e.id),
            "source_node_id": str(e.source_node_id),
            "target_node_id": str(e.target_node_id),
            "edge_type": e.edge_type.value,
            "strength": e.strength,
        } for e in edges],
    }


@router.get("/edges")
async def list_edges(
    edge_type: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(GraphEdge).order_by(GraphEdge.created_at.desc())

    if edge_type:
        query = query.where(GraphEdge.edge_type == edge_type)
    if cursor:
        cursor_id = decode_cursor(cursor)
        cursor_edge = await db.execute(select(GraphEdge).where(GraphEdge.id == cursor_id))
        ce = cursor_edge.scalar_one_or_none()
        if ce:
            query = query.where(GraphEdge.created_at < ce.created_at)

    result = await db.execute(query.limit(limit + 1))
    edges = list(result.scalars().all())
    has_more = len(edges) > limit
    items = edges[:limit]
    next_cursor = encode_cursor(items[-1].id) if has_more and items else None

    return {
        "items": [{
            "id": str(e.id),
            "source_node_id": str(e.source_node_id),
            "target_node_id": str(e.target_node_id),
            "edge_type": e.edge_type.value,
            "strength": e.strength,
            "created_at": e.created_at.isoformat(),
        } for e in items],
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


@router.get("/gaps")
async def get_gaps(db: AsyncSession = Depends(get_db)):
    from app.services.gap_detector import find_gaps
    return await find_gaps(db)


@router.get("/subgraph/{topic}")
async def get_subgraph(topic: str, db: AsyncSession = Depends(get_db)):
    # Search nodes containing topic keywords
    result = await db.execute(
        select(GraphNode).where(GraphNode.content.ilike(f"%{topic}%")).limit(50)
    )
    nodes = list(result.scalars().all())
    node_ids = {n.id for n in nodes}

    # Get edges between these nodes
    if node_ids:
        edges_result = await db.execute(
            select(GraphEdge).where(
                GraphEdge.source_node_id.in_(node_ids) | GraphEdge.target_node_id.in_(node_ids)
            )
        )
        edges = list(edges_result.scalars().all())
    else:
        edges = []

    return {
        "topic": topic,
        "nodes": [{
            "id": str(n.id),
            "node_type": n.node_type.value,
            "content": n.content,
            "quality_score": n.quality_score,
        } for n in nodes],
        "edges": [{
            "id": str(e.id),
            "source_node_id": str(e.source_node_id),
            "target_node_id": str(e.target_node_id),
            "edge_type": e.edge_type.value,
            "strength": e.strength,
        } for e in edges],
    }


@router.get("/convergence")
async def get_convergence(db: AsyncSession = Depends(get_db)):
    """Platform-wide convergence index."""
    # Count total nodes and edges
    node_count = await db.execute(select(sa_func.count(GraphNode.id)))
    edge_count = await db.execute(select(sa_func.count(GraphEdge.id)))

    # Count contradicts vs supports edges
    supports = await db.execute(
        select(sa_func.count(GraphEdge.id)).where(GraphEdge.edge_type == GraphEdgeType.SUPPORTS)
    )
    contradicts = await db.execute(
        select(sa_func.count(GraphEdge.id)).where(GraphEdge.edge_type == GraphEdgeType.CONTRADICTS)
    )

    total_nodes = node_count.scalar() or 0
    total_edges = edge_count.scalar() or 0
    support_count = supports.scalar() or 0
    contradict_count = contradicts.scalar() or 0

    # Convergence = ratio of supports to total directional edges
    directional = support_count + contradict_count
    convergence_index = support_count / max(directional, 1)

    return {
        "convergence_index": round(convergence_index, 3),
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "supports_count": support_count,
        "contradicts_count": contradict_count,
    }
