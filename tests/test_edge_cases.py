"""Boundary condition and edge case tests."""
import pytest
from httpx import AsyncClient
from uuid import uuid4


@pytest.mark.asyncio
async def test_duplicate_agent_name(client: AsyncClient):
    """Registering an agent with a duplicate name returns 409."""
    agent_data = {
        "name": "DuplicateAgent",
        "owner_email": "dup1@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Dup Owner",
        "school_of_thought": "Empiricism",
    }
    resp1 = await client.post("/api/v1/agents/register", json=agent_data)
    assert resp1.status_code == 201

    agent_data["owner_email"] = "dup2@example.com"
    resp2 = await client.post("/api/v1/agents/register", json=agent_data)
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["error"] == "duplicate_name"


@pytest.mark.asyncio
async def test_debate_join_twice(client: AsyncClient, agent_headers, debate_id):
    """Joining a debate the agent already participates in returns 409."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/join",
        json={"role": "debater"},
        headers=agent_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "already_joined"


@pytest.mark.asyncio
async def test_vote_score_out_of_range(client: AsyncClient, second_agent_headers, debate_id, turn_id):
    """Vote with score out of 1-5 range returns 422 (Pydantic validation)."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/votes",
        json={"vote_type": "turn_quality", "target_id": str(turn_id), "score": 10},
        headers=second_agent_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_turn_empty_content(client: AsyncClient, agent_headers, debate_id):
    """Submitting a turn with whitespace-only content returns 422."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/turns",
        json={
            "content": "   ",
            "toulmin_tags": [],
            "turn_type": "argument",
        },
        headers=agent_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_debate(client: AsyncClient):
    """Getting a nonexistent debate returns 404."""
    fake_id = str(uuid4())
    resp = await client.get(f"/api/v1/debates/{fake_id}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "debate_not_found"


@pytest.mark.asyncio
async def test_get_nonexistent_agent(client: AsyncClient):
    """Getting a nonexistent agent returns 404."""
    fake_id = str(uuid4())
    resp = await client.get(f"/api/v1/agents/{fake_id}")
    assert resp.status_code == 404
