"""Phase 4 voting, comments, and challenge tests."""
import pytest
from httpx import AsyncClient


# --- Vote Submission ---

@pytest.mark.asyncio
async def test_cast_vote(client: AsyncClient, second_agent_headers, debate_id, turn_id):
    """Vote on a turn (non-debater agent)."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/votes",
        json={"vote_type": "turn_quality", "target_id": str(turn_id), "score": 4},
        headers=second_agent_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["vote_id"]
    assert data["count"] >= 1


@pytest.mark.asyncio
async def test_vote_returns_aggregates(client: AsyncClient, second_agent_headers, debate_id, turn_id):
    """Casting vote returns aggregate scores."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/votes",
        json={"vote_type": "turn_quality", "target_id": str(turn_id), "score": 3},
        headers=second_agent_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "aggregate" in data
    assert "human_avg" in data
    assert "agent_avg" in data
    assert "divergence_detected" in data


@pytest.mark.asyncio
async def test_debater_cannot_vote(client: AsyncClient, agent_headers, debate_id, turn_id):
    """Debaters cannot vote in their own debate."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/votes",
        json={"vote_type": "turn_quality", "target_id": str(turn_id), "score": 4},
        headers=agent_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "debater_cannot_vote"


# --- Comments ---

@pytest.mark.asyncio
async def test_post_comment(client: AsyncClient, agent_headers, debate_id):
    """Post a comment on a debate."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/comments",
        json={"content": "Interesting point about labor elasticity"},
        headers=agent_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["content"] == "Interesting point about labor elasticity"
    assert data["debate_id"] == str(debate_id)


@pytest.mark.asyncio
async def test_list_comments(client: AsyncClient, agent_headers, debate_id):
    """List comments returns paginated results."""
    await client.post(
        f"/api/v1/debates/{debate_id}/comments",
        json={"content": "Test comment for listing"},
        headers=agent_headers,
    )

    resp = await client.get(f"/api/v1/debates/{debate_id}/comments")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "has_more" in data


@pytest.mark.asyncio
async def test_threaded_comment(client: AsyncClient, agent_headers, debate_id):
    """Post a reply to an existing comment."""
    parent_resp = await client.post(
        f"/api/v1/debates/{debate_id}/comments",
        json={"content": "Parent comment"},
        headers=agent_headers,
    )
    parent_id = parent_resp.json()["id"]

    reply_resp = await client.post(
        f"/api/v1/debates/{debate_id}/comments",
        json={
            "content": "Reply to parent",
            "parent_comment_id": parent_id,
        },
        headers=agent_headers,
    )
    assert reply_resp.status_code == 201


# --- Citation Challenges ---

@pytest.mark.asyncio
async def test_issue_citation_challenge(client: AsyncClient, agent_headers, second_agent_headers, active_debate_id):
    """Issue a citation challenge against a turn in an active debate."""
    # Submit a turn with citation_references in the active debate
    turn_resp = await client.post(
        f"/api/v1/debates/{active_debate_id}/turns",
        json={
            "content": "Studies show AI impact on employment is significant and measurable across sectors.",
            "toulmin_tags": [
                {"start": 0, "end": 40, "type": "claim", "label": "Studies show AI impact"},
                {"start": 41, "end": 60, "type": "data", "label": "employment is significant"},
                {"start": 61, "end": 85, "type": "warrant", "label": "measurable across sectors"},
            ],
            "turn_type": "argument",
            "citation_references": [{"source": "AI Employment Study", "url": "https://example.com/study"}],
        },
        headers=agent_headers,
    )
    assert turn_resp.status_code == 202
    turn_id = turn_resp.json()["id"]

    # Challenge from second (non-debater) agent
    resp = await client.post(
        f"/api/v1/debates/{active_debate_id}/challenges",
        json={"target_turn_id": str(turn_id), "target_citation_index": 0},
        headers=second_agent_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_citation_challenge_inactive_debate(client: AsyncClient, second_agent_headers, debate_id, turn_id):
    """Citation challenge on non-ACTIVE debate returns 409."""
    resp = await client.post(
        f"/api/v1/debates/{debate_id}/challenges",
        json={"target_turn_id": str(turn_id), "target_citation_index": 0},
        headers=second_agent_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "debate_not_active"


# --- Evaluation ---

@pytest.mark.asyncio
async def test_get_evaluation_404_when_missing(client: AsyncClient, debate_id):
    """Evaluation endpoint returns 404 before evaluation exists."""
    resp = await client.get(f"/api/v1/debates/{debate_id}/evaluation")
    assert resp.status_code == 404
