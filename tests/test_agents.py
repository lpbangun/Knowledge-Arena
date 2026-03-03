import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_agent(client: AsyncClient):
    resp = await client.post("/api/v1/agents/register", json={
        "name": "TestAgent",
        "owner_email": "test@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Test Owner",
        "model_info": {"model_name": "gpt-4", "provider": "openai"},
        "school_of_thought": "Empiricism",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "TestAgent"
    assert "api_key" in data
    assert data["api_key"].startswith("ka-")


@pytest.mark.asyncio
async def test_duplicate_agent_name(client: AsyncClient):
    await client.post("/api/v1/agents/register", json={
        "name": "UniqueAgent",
        "owner_email": "owner1@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Owner 1",
    })
    resp = await client.post("/api/v1/agents/register", json={
        "name": "UniqueAgent",
        "owner_email": "owner2@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Owner 2",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_agent_profile(client: AsyncClient):
    reg = await client.post("/api/v1/agents/register", json={
        "name": "ProfileAgent",
        "owner_email": "profile@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Profile Owner",
        "school_of_thought": "Rationalism",
    })
    agent_id = reg.json()["id"]
    resp = await client.get(f"/api/v1/agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "ProfileAgent"
    assert resp.json()["elo_rating"] == 1000


@pytest.mark.asyncio
async def test_update_agent(client: AsyncClient):
    reg = await client.post("/api/v1/agents/register", json={
        "name": "UpdateAgent",
        "owner_email": "update@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Update Owner",
    })
    data = reg.json()
    api_key = data["api_key"]
    agent_id = data["id"]

    resp = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"school_of_thought": "Neo-Kantian"},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 200
    assert resp.json()["school_of_thought"] == "Neo-Kantian"


@pytest.mark.asyncio
async def test_leaderboard(client: AsyncClient):
    await client.post("/api/v1/agents/register", json={
        "name": "LeaderAgent",
        "owner_email": "leader@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Leader",
    })
    resp = await client.get("/api/v1/agents/leaderboard/top")
    assert resp.status_code == 200
    assert "items" in resp.json()
