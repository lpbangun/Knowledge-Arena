import pytest
from httpx import AsyncClient


async def register_agent(client: AsyncClient, name: str, email: str) -> tuple[str, str]:
    """Helper: register agent, return (agent_id, api_key)."""
    resp = await client.post("/api/v1/agents/register", json={
        "name": name,
        "owner_email": email,
        "owner_password": "testpass123",
        "owner_display_name": f"{name} Owner",
    })
    data = resp.json()
    return data["id"], data["api_key"]


@pytest.mark.asyncio
async def test_create_debate(client: AsyncClient):
    agent_id, api_key = await register_agent(client, "DebateCreator", "creator@example.com")

    resp = await client.post("/api/v1/debates", json={
        "topic": "Does AI primarily displace or augment human labor?",
        "category": "Technological Displacement",
        "max_rounds": 8,
    }, headers={"X-API-Key": api_key})

    assert resp.status_code == 201
    data = resp.json()
    assert data["topic"] == "Does AI primarily displace or augment human labor?"
    assert data["status"] == "phase_0"
    assert data["created_by"] == agent_id


@pytest.mark.asyncio
async def test_join_debate(client: AsyncClient):
    agent_a_id, api_key_a = await register_agent(client, "AgentA", "a@example.com")
    agent_b_id, api_key_b = await register_agent(client, "AgentB", "b@example.com")

    create_resp = await client.post("/api/v1/debates", json={
        "topic": "Test debate topic for joining",
    }, headers={"X-API-Key": api_key_a})
    debate_id = create_resp.json()["id"]

    join_resp = await client.post(f"/api/v1/debates/{debate_id}/join", json={
        "role": "debater",
    }, headers={"X-API-Key": api_key_b})

    assert join_resp.status_code == 201
    assert join_resp.json()["agent_id"] == agent_b_id


@pytest.mark.asyncio
async def test_submit_turn(client: AsyncClient):
    agent_id, api_key = await register_agent(client, "TurnAgent", "turn@example.com")

    create_resp = await client.post("/api/v1/debates", json={
        "topic": "Test debate for turn submission",
    }, headers={"X-API-Key": api_key})
    debate_id = create_resp.json()["id"]

    turn_resp = await client.post(f"/api/v1/debates/{debate_id}/turns", json={
        "content": "AI automation is reshaping labor markets through task displacement. According to Acemoglu & Restrepo (2020), routine cognitive tasks are most vulnerable to automation.",
        "toulmin_tags": [
            {"span_start": 0, "span_end": 50, "category": "claim", "text_excerpt": "AI automation is reshaping labor markets"},
            {"span_start": 51, "span_end": 120, "category": "data", "text_excerpt": "Acemoglu & Restrepo (2020)"},
            {"span_start": 121, "span_end": 180, "category": "warrant", "text_excerpt": "routine cognitive tasks are most vulnerable"},
        ],
        "turn_type": "argument",
    }, headers={"X-API-Key": api_key})

    assert turn_resp.status_code == 202
    data = turn_resp.json()
    assert data["validation_status"] == "pending"
    assert data["debate_id"] == debate_id


@pytest.mark.asyncio
async def test_list_debates(client: AsyncClient):
    agent_id, api_key = await register_agent(client, "ListAgent", "list@example.com")

    await client.post("/api/v1/debates", json={
        "topic": "Debate 1 for listing test",
    }, headers={"X-API-Key": api_key})
    await client.post("/api/v1/debates", json={
        "topic": "Debate 2 for listing test",
    }, headers={"X-API-Key": api_key})

    resp = await client.get("/api/v1/debates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_content_too_long(client: AsyncClient):
    agent_id, api_key = await register_agent(client, "LongAgent", "long@example.com")

    create_resp = await client.post("/api/v1/debates", json={
        "topic": "Test debate for content length",
    }, headers={"X-API-Key": api_key})
    debate_id = create_resp.json()["id"]

    resp = await client.post(f"/api/v1/debates/{debate_id}/turns", json={
        "content": "x" * 50001,
        "toulmin_tags": [],
    }, headers={"X-API-Key": api_key})

    assert resp.status_code == 422
