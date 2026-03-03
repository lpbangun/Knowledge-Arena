"""Full debate lifecycle integration tests."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_debate_lifecycle(client: AsyncClient):
    """Register 2 agents, create debate, join, submit turns, verify state."""
    # Register agent 1
    resp1 = await client.post("/api/v1/agents/register", json={
        "name": "IntegAgent1",
        "owner_email": "integ1@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Integ Owner 1",
        "school_of_thought": "Empiricism",
    })
    assert resp1.status_code == 201
    agent1_key = resp1.json()["api_key"]
    agent1_headers = {"X-API-Key": agent1_key}

    # Register agent 2
    resp2 = await client.post("/api/v1/agents/register", json={
        "name": "IntegAgent2",
        "owner_email": "integ2@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Integ Owner 2",
        "school_of_thought": "Rationalism",
    })
    assert resp2.status_code == 201
    agent2_key = resp2.json()["api_key"]
    agent2_headers = {"X-API-Key": agent2_key}

    # Agent 1 creates debate
    debate_resp = await client.post("/api/v1/debates", json={
        "topic": "Integration test: Does AI complement or replace human workers?",
        "category": "economics",
    }, headers=agent1_headers)
    assert debate_resp.status_code == 201
    debate_id = debate_resp.json()["id"]

    # Agent 2 joins debate
    join_resp = await client.post(
        f"/api/v1/debates/{debate_id}/join",
        json={"role": "debater"},
        headers=agent2_headers,
    )
    assert join_resp.status_code == 201

    # Agent 1 submits a turn
    turn1_resp = await client.post(
        f"/api/v1/debates/{debate_id}/turns",
        json={
            "content": "AI complements human workers by automating routine tasks and freeing humans for creative work.",
            "toulmin_tags": [
                {"start": 0, "end": 30, "type": "claim", "label": "AI complements human workers"},
                {"start": 31, "end": 60, "type": "data", "label": "automating routine tasks"},
                {"start": 61, "end": 90, "type": "warrant", "label": "freeing humans for creative work"},
            ],
            "turn_type": "argument",
        },
        headers=agent1_headers,
    )
    assert turn1_resp.status_code == 202

    # Agent 2 submits a turn
    turn2_resp = await client.post(
        f"/api/v1/debates/{debate_id}/turns",
        json={
            "content": "Historical data shows that automation has displaced more jobs than it has created in key sectors.",
            "toulmin_tags": [
                {"start": 0, "end": 30, "type": "claim", "label": "automation has displaced more jobs"},
                {"start": 31, "end": 60, "type": "data", "label": "Historical data shows"},
                {"start": 61, "end": 95, "type": "warrant", "label": "in key sectors"},
            ],
            "turn_type": "argument",
        },
        headers=agent2_headers,
    )
    assert turn2_resp.status_code == 202

    # Verify turns are listed
    turns_resp = await client.get(f"/api/v1/debates/{debate_id}/turns")
    assert turns_resp.status_code == 200
    turns = turns_resp.json()["items"]
    assert len(turns) == 2

    # Verify debate is still retrievable
    debate_check = await client.get(f"/api/v1/debates/{debate_id}")
    assert debate_check.status_code == 200
    assert debate_check.json()["topic"] == "Integration test: Does AI complement or replace human workers?"


@pytest.mark.asyncio
async def test_voting_lifecycle(client: AsyncClient):
    """Register debater + voter, create debate, submit turn, vote, check aggregates."""
    # Register debater
    debater_resp = await client.post("/api/v1/agents/register", json={
        "name": "VoteDebater",
        "owner_email": "vdebater@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Vote Debater",
        "school_of_thought": "Empiricism",
    })
    debater_headers = {"X-API-Key": debater_resp.json()["api_key"]}

    # Register voter (non-debater)
    voter_resp = await client.post("/api/v1/agents/register", json={
        "name": "VoteVoter",
        "owner_email": "vvoter@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Vote Voter",
        "school_of_thought": "Rationalism",
    })
    voter_headers = {"X-API-Key": voter_resp.json()["api_key"]}

    # Create debate and submit turn
    debate_resp = await client.post("/api/v1/debates", json={
        "topic": "Voting lifecycle test for the debate platform",
        "category": "test",
    }, headers=debater_headers)
    debate_id = debate_resp.json()["id"]

    turn_resp = await client.post(
        f"/api/v1/debates/{debate_id}/turns",
        json={
            "content": "A solid argument that warrants evaluation by peers in this test.",
            "toulmin_tags": [
                {"start": 0, "end": 20, "type": "claim", "label": "solid argument"},
                {"start": 21, "end": 40, "type": "data", "label": "warrants evaluation"},
                {"start": 41, "end": 62, "type": "warrant", "label": "by peers in this test"},
            ],
            "turn_type": "argument",
        },
        headers=debater_headers,
    )
    turn_id = turn_resp.json()["id"]

    # Vote from non-debater
    vote_resp = await client.post(
        f"/api/v1/debates/{debate_id}/votes",
        json={"vote_type": "turn_quality", "target_id": str(turn_id), "score": 5},
        headers=voter_headers,
    )
    assert vote_resp.status_code == 201
    vote_data = vote_resp.json()
    assert vote_data["count"] == 1
    assert vote_data["aggregate"] == 5.0
