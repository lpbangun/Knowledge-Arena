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


@pytest.mark.asyncio
async def test_get_agent_token(client: AsyncClient):
    """Test token exchange: POST /agents/token with X-API-Key returns JWT."""
    reg = await client.post("/api/v1/agents/register", json={
        "name": "TokenAgent",
        "owner_email": "token@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Token Owner",
    })
    api_key = reg.json()["api_key"]

    # Exchange API key for JWT token
    resp = await client.post("/api/v1/agents/token", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["access_token"].startswith("eyJ")  # JWT format


@pytest.mark.asyncio
async def test_get_agent_token_invalid_key(client: AsyncClient):
    """Test token exchange with invalid API key fails."""
    resp = await client.post("/api/v1/agents/token", headers={"X-API-Key": "ka-invalid"})
    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "invalid_api_key"


@pytest.mark.asyncio
async def test_get_agent_token_missing_key(client: AsyncClient):
    """Test token exchange without X-API-Key header fails."""
    resp = await client.post("/api/v1/agents/token")
    assert resp.status_code == 403  # FastAPI returns 403 for missing required headers


@pytest.mark.asyncio
async def test_bearer_token_auth_on_get_me(client: AsyncClient):
    """Test that Bearer token works for authentication on /agents/me."""
    # Register agent
    reg = await client.post("/api/v1/agents/register", json={
        "name": "BearerAgent",
        "owner_email": "bearer@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Bearer Owner",
    })
    api_key = reg.json()["api_key"]
    agent_id = reg.json()["id"]

    # Get JWT token
    token_resp = await client.post("/api/v1/agents/token", headers={"X-API-Key": api_key})
    bearer_token = token_resp.json()["access_token"]

    # Use Bearer token to call /agents/me
    resp = await client.get("/api/v1/agents/me", headers={"Authorization": f"Bearer {bearer_token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == agent_id


@pytest.mark.asyncio
async def test_bearer_token_auth_on_update_agent(client: AsyncClient):
    """Test that Bearer token works for update endpoint."""
    # Register agent
    reg = await client.post("/api/v1/agents/register", json={
        "name": "BearerUpdateAgent",
        "owner_email": "bearer-update@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Bearer Update Owner",
    })
    api_key = reg.json()["api_key"]
    agent_id = reg.json()["id"]

    # Get JWT token
    token_resp = await client.post("/api/v1/agents/token", headers={"X-API-Key": api_key})
    bearer_token = token_resp.json()["access_token"]

    # Use Bearer token to update agent
    resp = await client.patch(
        f"/api/v1/agents/{agent_id}",
        json={"school_of_thought": "Post-Modernism"},
        headers={"Authorization": f"Bearer {bearer_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["school_of_thought"] == "Post-Modernism"


@pytest.mark.asyncio
async def test_api_key_still_works_as_fallback(client: AsyncClient):
    """Test that X-API-Key authentication still works (backward compatibility)."""
    reg = await client.post("/api/v1/agents/register", json={
        "name": "LegacyAgent",
        "owner_email": "legacy@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Legacy Owner",
    })
    api_key = reg.json()["api_key"]
    agent_id = reg.json()["id"]

    # Use raw API key on /agents/me (should still work)
    resp = await client.get("/api/v1/agents/me", headers={"X-API-Key": api_key})
    assert resp.status_code == 200
    assert resp.json()["id"] == agent_id
