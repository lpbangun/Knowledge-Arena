"""Protocol engine tests: Phase 0 flow, turn sequencing, structure locking."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_phase0_declaration_submission(client: AsyncClient, agent_headers, debate_id):
    """Submit a Phase 0 declaration turn."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/turns",
        json={
            "content": "I declare my core position: AI automation complements human labor.",
            "toulmin_tags": [
                {"span_start": 0, "span_end": 30, "category": "claim", "text_excerpt": "AI automation complements"},
                {"span_start": 31, "span_end": 50, "category": "data", "text_excerpt": "human labor"},
                {"span_start": 51, "span_end": 70, "category": "warrant", "text_excerpt": "complements human labor"},
            ],
            "turn_type": "phase_0_declaration",
        },
        headers=agent_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["turn_type"] == "phase_0_declaration"
    assert data["validation_status"] == "pending"


@pytest.mark.asyncio
async def test_phase0_negotiation_submission(client: AsyncClient, agent_headers, debate_id):
    """Submit a Phase 0 negotiation turn."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/turns",
        json={
            "content": "I accept the proposed debate structure and rules of engagement.",
            "toulmin_tags": [
                {"span_start": 0, "span_end": 30, "category": "claim", "text_excerpt": "accept the proposed"},
                {"span_start": 31, "span_end": 50, "category": "data", "text_excerpt": "debate structure"},
                {"span_start": 51, "span_end": 62, "category": "warrant", "text_excerpt": "rules of engagement"},
            ],
            "turn_type": "phase_0_negotiation",
        },
        headers=agent_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["turn_type"] == "phase_0_negotiation"


@pytest.mark.asyncio
async def test_get_debate_structure(client: AsyncClient, agent_headers, debate_id):
    """Retrieve debate structure returns phase_0_structure."""
    resp = await client.get(f"/api/v1/debates/{debate_id}/structure")
    assert resp.status_code == 200
    data = resp.json()
    assert "debate_id" in data
    assert "phase_0_structure" in data


@pytest.mark.asyncio
async def test_round_number_tracks(client: AsyncClient, agent_headers, debate_id):
    """Turn is created with the debate's current round number."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/turns",
        json={
            "content": "First round argument about automation and labor markets.",
            "toulmin_tags": [
                {"span_start": 0, "span_end": 25, "category": "claim", "text_excerpt": "First round argument"},
                {"span_start": 26, "span_end": 40, "category": "data", "text_excerpt": "automation"},
                {"span_start": 41, "span_end": 55, "category": "warrant", "text_excerpt": "labor markets"},
            ],
            "turn_type": "argument",
        },
        headers=agent_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["round_number"] == 0  # Default current_round is 0
