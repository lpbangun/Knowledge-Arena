"""Evolution timeline and learnings (BUP) tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_evolution_timeline_empty(client: AsyncClient, agent_headers):
    """Evolution timeline for a new agent returns empty data."""
    # Get agent_id from registration
    resp = await client.post("/api/v1/agents/register", json={
        "name": "EvolutionTestAgent",
        "owner_email": "evo@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Evo Owner",
        "school_of_thought": "Pragmatism",
    })
    agent_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/agents/{agent_id}/evolution")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_learnings_endpoint(client: AsyncClient, agent_headers):
    """Get learnings for own agent returns data."""
    # Register and get agent_id
    resp = await client.post("/api/v1/agents/register", json={
        "name": "LearningsTestAgent",
        "owner_email": "learn@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Learn Owner",
        "school_of_thought": "Empiricism",
    })
    agent_id = resp.json()["id"]
    headers = {"X-API-Key": resp.json()["api_key"]}

    resp = await client.get(f"/api/v1/agents/{agent_id}/learnings", headers=headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_learnings_forbidden_for_other_agent(client: AsyncClient, agent_headers):
    """Cannot access another agent's learnings."""
    # Register a different agent
    resp = await client.post("/api/v1/agents/register", json={
        "name": "OtherLearningAgent",
        "owner_email": "other_learn@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Other",
        "school_of_thought": "Rationalism",
    })
    other_id = resp.json()["id"]

    # Try to access with original agent's headers
    resp = await client.get(f"/api/v1/agents/{other_id}/learnings", headers=agent_headers)
    assert resp.status_code == 403
