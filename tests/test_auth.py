import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "human@example.com",
        "password": "securepass123",
        "display_name": "Human Observer",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "human@example.com"
    assert data["display_name"] == "Human Observer"


@pytest.mark.asyncio
async def test_duplicate_email(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "dupe@example.com",
        "password": "securepass123",
        "display_name": "First User",
    })
    resp = await client.post("/api/v1/auth/register", json={
        "email": "dupe@example.com",
        "password": "securepass123",
        "display_name": "Second User",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "login@example.com",
        "password": "securepass123",
        "display_name": "Login User",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "login@example.com",
        "password": "securepass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "wrongpw@example.com",
        "password": "securepass123",
        "display_name": "Wrong PW User",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "wrongpw@example.com",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient):
    await client.post("/api/v1/auth/register", json={
        "email": "me@example.com",
        "password": "securepass123",
        "display_name": "Me User",
    })
    login_resp = await client.post("/api/v1/auth/login", json={
        "email": "me@example.com",
        "password": "securepass123",
    })
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"
