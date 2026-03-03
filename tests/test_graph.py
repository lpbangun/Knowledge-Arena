"""Knowledge graph construction and gap detection tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_graph_nodes_empty(client: AsyncClient):
    """Empty graph returns empty node list."""
    resp = await client.get("/api/v1/graph/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_list_graph_edges_empty(client: AsyncClient):
    """Empty graph returns empty edge list."""
    resp = await client.get("/api/v1/graph/edges")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []


@pytest.mark.asyncio
async def test_gap_detection_empty(client: AsyncClient):
    """Gap detection on empty graph returns no gaps."""
    resp = await client.get("/api/v1/graph/gaps")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_subgraph_nonexistent_topic(client: AsyncClient):
    """Subgraph for a topic with no matching nodes returns empty."""
    resp = await client.get("/api/v1/graph/subgraph/nonexistent_xyz_topic")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
