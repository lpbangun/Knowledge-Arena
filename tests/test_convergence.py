"""Convergence detection signal tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_convergence_not_detected_early(client: AsyncClient, debate_id):
    """A new debate should not have convergence signals yet."""
    resp = await client.get(f"/api/v1/debates/{debate_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["convergence_signals"] is None


@pytest.mark.asyncio
async def test_convergence_endpoint_returns_data(client: AsyncClient):
    """Knowledge graph convergence endpoint returns response."""
    resp = await client.get("/api/v1/graph/convergence")
    assert resp.status_code == 200
