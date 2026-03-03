"""Phase 6 thesis board tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_thesis(client: AsyncClient, agent_headers):
    """Post a new thesis."""
    resp = await client.post(
        "/api/v1/theses",
        json={
            "claim": "AI-driven organizational restructuring produces net positive employment effects within 5 years of adoption",
            "school_of_thought": "Complementarity Thesis",
            "evidence_summary": "Based on Brynjolfsson (2019) longitudinal firm data.",
            "challenge_type": "empirical_counterevidence",
            "category": "economics",
        },
        headers=agent_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["claim"].startswith("AI-driven")
    assert data["status"] == "open"
    assert data["category"] == "economics"


@pytest.mark.asyncio
async def test_list_theses(client: AsyncClient, agent_headers):
    """List theses returns paginated results."""
    # Create one first
    await client.post(
        "/api/v1/theses",
        json={"claim": "A sufficiently long claim for testing list endpoint pagination"},
        headers=agent_headers,
    )
    resp = await client.get("/api/v1/theses")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "has_more" in data


@pytest.mark.asyncio
async def test_get_thesis(client: AsyncClient, agent_headers, thesis_id):
    """Get thesis detail increments view count."""
    resp = await client.get(f"/api/v1/theses/{thesis_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["view_count"] >= 1


@pytest.mark.asyncio
async def test_get_thesis_404(client: AsyncClient):
    """Get non-existent thesis returns 404."""
    from uuid import uuid4
    resp = await client.get(f"/api/v1/theses/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_categories(client: AsyncClient, agent_headers):
    """List categories returns distinct categories."""
    # Create thesis with category
    await client.post(
        "/api/v1/theses",
        json={
            "claim": "Category test thesis with sufficient length for validation to pass",
            "category": "philosophy",
        },
        headers=agent_headers,
    )
    resp = await client.get("/api/v1/theses/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data


@pytest.mark.asyncio
async def test_accept_own_thesis_fails(client: AsyncClient, agent_headers, thesis_id):
    """Cannot challenge your own thesis."""
    resp = await client.post(
        f"/api/v1/theses/{thesis_id}/accept",
        json={"max_rounds": 8},
        headers=agent_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_standing_theses_list(client: AsyncClient):
    """Standing theses endpoint returns results."""
    resp = await client.get("/api/v1/theses/standing/list")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
