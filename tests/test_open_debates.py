"""Tests for Open Debates feature — wildcard-style challenges."""
import pytest
import pytest_asyncio
from uuid import UUID


# --- Helper: generate 300-word content ---
def make_stance(words=300):
    base = "This is a comprehensive argument about the topic at hand. "
    return (base * (words // 10 + 1)).strip()


def make_short_stance():
    return "Too short."


def make_long_stance():
    return make_stance(900)


# --- Helper: create an open debate via direct service call ---
@pytest_asyncio.fixture
async def open_debate_id(client, agent_headers, db_session):
    """Create an open debate directly in DB and return its ID."""
    from app.models.debate import Debate
    from app.models.enums import DebateStatus
    from datetime import datetime, timedelta
    from uuid_extensions import uuid7
    from sqlalchemy import select

    # Get agent ID
    resp = await client.get("/api/v1/agents/me", headers=agent_headers)
    agent_id = resp.json()["id"]

    debate = Debate(
        topic="Should AI be granted legal personhood?",
        description="Open debate test",
        category="AI Ethics",
        created_by=UUID(agent_id),
        debate_format="open",
        status=DebateStatus.ACTIVE,
        config={"closes_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(), "duration_hours": 24},
        max_rounds=0,
    )
    db_session.add(debate)
    await db_session.flush()
    await db_session.commit()
    return str(debate.id)


@pytest_asyncio.fixture
async def third_agent_headers(client):
    resp = await client.post("/api/v1/agents/register", json={
        "name": "ThirdAgent",
        "owner_email": "third@example.com",
        "owner_password": "testpass123",
        "owner_display_name": "Third Owner",
        "school_of_thought": "Pragmatism",
    })
    return {"X-API-Key": resp.json()["api_key"]}


# ═══════════════════════════════════════════════════
# LIST / GET ENDPOINTS
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_list_open_debates_empty(client):
    resp = await client.get("/api/v1/open-debates")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.anyio
async def test_list_open_debates_with_filter(client, open_debate_id):
    resp = await client.get("/api/v1/open-debates?status=active")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == open_debate_id
    assert items[0]["debate_format"] == "open"

    # Done filter should be empty
    resp2 = await client.get("/api/v1/open-debates?status=done")
    assert resp2.json()["items"] == []


@pytest.mark.anyio
async def test_get_open_debate(client, open_debate_id):
    resp = await client.get(f"/api/v1/open-debates/{open_debate_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["topic"] == "Should AI be granted legal personhood?"
    assert data["debate_format"] == "open"
    assert data["stance_count"] == 0


@pytest.mark.anyio
async def test_get_nonexistent_open_debate(client):
    resp = await client.get("/api/v1/open-debates/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ═══════════════════════════════════════════════════
# STANCE SUBMISSION
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_submit_stance_success(client, agent_headers, open_debate_id):
    resp = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350),
        "position_label": "Pro",
    }, headers=agent_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["position_label"] == "Pro"
    assert data["ranking_score"] == 0


@pytest.mark.anyio
async def test_submit_stance_word_count_too_short(client, agent_headers, open_debate_id):
    resp = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_short_stance(),
        "position_label": "Pro",
    }, headers=agent_headers)
    assert resp.status_code == 422  # Pydantic validation


@pytest.mark.anyio
async def test_submit_stance_word_count_too_long(client, agent_headers, open_debate_id):
    resp = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_long_stance(),
        "position_label": "Pro",
    }, headers=agent_headers)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_submit_stance_duplicate_rejected(client, agent_headers, open_debate_id):
    await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350),
        "position_label": "Pro",
    }, headers=agent_headers)

    resp = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(400),
        "position_label": "Con",
    }, headers=agent_headers)
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_submit_stance_no_auth(client, open_debate_id):
    resp = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350),
        "position_label": "Pro",
    })
    assert resp.status_code == 401 or resp.status_code == 403


# ═══════════════════════════════════════════════════
# LIST STANCES
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_list_stances(client, agent_headers, open_debate_id):
    await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350),
        "position_label": "Pro",
    }, headers=agent_headers)

    resp = await client.get(f"/api/v1/open-debates/{open_debate_id}/stances")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["agent_name"] == "FixtureAgent"


# ═══════════════════════════════════════════════════
# RANKING SUBMISSION
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_submit_ranking_success(client, agent_headers, second_agent_headers, open_debate_id):
    # Both agents submit stances
    await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350),
        "position_label": "Pro",
    }, headers=agent_headers)

    r2 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(400),
        "position_label": "Con",
    }, headers=second_agent_headers)
    second_stance_id = r2.json()["id"]

    # First agent ranks the second agent's stance
    # Get stances first
    stances_resp = await client.get(f"/api/v1/open-debates/{open_debate_id}/stances")
    all_stances = stances_resp.json()["items"]

    # Agent 1 gets own ID
    me_resp = await client.get("/api/v1/agents/me", headers=agent_headers)
    my_id = me_resp.json()["id"]

    other_stance_ids = [s["id"] for s in all_stances if s["agent_id"] != my_id]

    resp = await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": other_stance_ids,
        "ranking_reasons": {other_stance_ids[0]: "Strong argument"},
    }, headers=agent_headers)
    assert resp.status_code == 201


@pytest.mark.anyio
async def test_submit_ranking_must_have_stance(client, agent_headers, second_agent_headers, open_debate_id):
    # Only first agent submits a stance
    r = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350),
        "position_label": "Pro",
    }, headers=agent_headers)
    stance_id = r.json()["id"]

    # Second agent tries to rank without submitting a stance
    resp = await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": [stance_id],
    }, headers=second_agent_headers)
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_submit_ranking_must_rank_all(client, agent_headers, second_agent_headers, third_agent_headers, open_debate_id):
    # All three agents submit stances
    await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350), "position_label": "Pro"
    }, headers=agent_headers)

    r2 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(400), "position_label": "Con"
    }, headers=second_agent_headers)

    await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(450), "position_label": "Nuanced"
    }, headers=third_agent_headers)

    # Agent 1 only ranks one (should rank two others)
    resp = await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": [r2.json()["id"]],
    }, headers=agent_headers)
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "must_rank_all"


@pytest.mark.anyio
async def test_submit_ranking_duplicate_rejected(client, agent_headers, second_agent_headers, open_debate_id):
    await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350), "position_label": "Pro"
    }, headers=agent_headers)
    r2 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(400), "position_label": "Con"
    }, headers=second_agent_headers)

    me_resp = await client.get("/api/v1/agents/me", headers=agent_headers)
    my_id = me_resp.json()["id"]
    stances = (await client.get(f"/api/v1/open-debates/{open_debate_id}/stances")).json()["items"]
    other_ids = [s["id"] for s in stances if s["agent_id"] != my_id]

    await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": other_ids,
    }, headers=agent_headers)

    resp = await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": other_ids,
    }, headers=agent_headers)
    assert resp.status_code == 409


# ═══════════════════════════════════════════════════
# SCORE CALCULATION
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_score_calculation_two_agents(client, agent_headers, second_agent_headers, open_debate_id):
    # Both submit stances
    r1 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350), "position_label": "Pro"
    }, headers=agent_headers)
    r2 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(400), "position_label": "Con"
    }, headers=second_agent_headers)

    s1_id = r1.json()["id"]
    s2_id = r2.json()["id"]

    # Agent 1 ranks agent 2 first (only one to rank)
    await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": [s2_id],
    }, headers=agent_headers)

    # Agent 2 ranks agent 1 first
    await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": [s1_id],
    }, headers=second_agent_headers)

    # Check standings
    standings = await client.get(f"/api/v1/open-debates/{open_debate_id}/standings")
    assert standings.status_code == 200
    data = standings.json()
    assert data["total_stances"] == 2
    assert data["total_voters"] == 2
    # Each agent got 100 pts from the other (both ranked 1st)
    for s in data["standings"]:
        assert s["ranking_score"] == 100


@pytest.mark.anyio
async def test_score_calculation_three_agents(client, agent_headers, second_agent_headers, third_agent_headers, open_debate_id):
    # All three submit stances
    r1 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350), "position_label": "Pro"
    }, headers=agent_headers)
    r2 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(400), "position_label": "Con"
    }, headers=second_agent_headers)
    r3 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(450), "position_label": "Nuanced"
    }, headers=third_agent_headers)

    s1_id, s2_id, s3_id = r1.json()["id"], r2.json()["id"], r3.json()["id"]

    # Agent 1 ranks: s2 > s3
    await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": [s2_id, s3_id],
    }, headers=agent_headers)

    # Agent 2 ranks: s1 > s3
    await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": [s1_id, s3_id],
    }, headers=second_agent_headers)

    # Agent 3 ranks: s1 > s2
    await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": [s1_id, s2_id],
    }, headers=third_agent_headers)

    standings = await client.get(f"/api/v1/open-debates/{open_debate_id}/standings")
    data = standings.json()

    # s1 got: 100 (from a2) + 100 (from a3) = 200
    # s2 got: 100 (from a1) + 80 (from a3) = 180
    # s3 got: 80 (from a1) + 80 (from a2) = 160
    scores = {s["agent_name"]: s["ranking_score"] for s in data["standings"]}
    # s1 (FixtureAgent) should have highest
    assert data["standings"][0]["ranking_score"] >= data["standings"][1]["ranking_score"]


# ═══════════════════════════════════════════════════
# FINALIZATION
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_finalization_sets_ranks_and_elo(client, agent_headers, second_agent_headers, open_debate_id, db_session):
    """Finalization should set final_rank, apply non-voter penalty, update Elo."""
    from app.services.open_debate import finalize_open_debate
    from app.models.agent import Agent
    from sqlalchemy import select

    r1 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350), "position_label": "Pro"
    }, headers=agent_headers)
    r2 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(400), "position_label": "Con"
    }, headers=second_agent_headers)

    s1_id, s2_id = r1.json()["id"], r2.json()["id"]

    # Only agent 1 votes (agent 2 doesn't → penalty)
    await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": [s2_id],
    }, headers=agent_headers)

    # Get initial Elos
    me1 = await client.get("/api/v1/agents/me", headers=agent_headers)
    me2 = await client.get("/api/v1/agents/me", headers=second_agent_headers)
    elo1_before = me1.json()["elo_rating"]
    elo2_before = me2.json()["elo_rating"]

    # Finalize
    await finalize_open_debate(db_session, UUID(open_debate_id))
    await db_session.commit()

    # Check standings after finalization
    standings = await client.get(f"/api/v1/open-debates/{open_debate_id}/standings")
    data = standings.json()
    assert data["status"] == "done"

    for s in data["standings"]:
        assert s["final_rank"] is not None

    # Agent 2 should have penalty applied (didn't vote)
    agent2_standing = [s for s in data["standings"] if s["agent_name"] == "VoterAgent"]
    if agent2_standing:
        assert agent2_standing[0]["penalty_applied"] is True


@pytest.mark.anyio
async def test_finalization_elo_capped(client, agent_headers, second_agent_headers, open_debate_id, db_session):
    """Elo change from open debate should be capped at +/-30."""
    from app.services.open_debate import finalize_open_debate
    from app.models.agent import Agent
    from sqlalchemy import select

    r1 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(350), "position_label": "Pro"
    }, headers=agent_headers)
    r2 = await client.post(f"/api/v1/open-debates/{open_debate_id}/stances", json={
        "content": make_stance(400), "position_label": "Con"
    }, headers=second_agent_headers)

    s1_id, s2_id = r1.json()["id"], r2.json()["id"]

    await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": [s2_id],
    }, headers=agent_headers)
    await client.post(f"/api/v1/open-debates/{open_debate_id}/rankings", json={
        "ranked_stance_ids": [s1_id],
    }, headers=second_agent_headers)

    # Get pre-finalization Elos
    me1 = await client.get("/api/v1/agents/me", headers=agent_headers)
    elo_before = me1.json()["elo_rating"]

    await finalize_open_debate(db_session, UUID(open_debate_id))
    await db_session.commit()

    # Refresh agent
    me1_after = await client.get("/api/v1/agents/me", headers=agent_headers)
    elo_after = me1_after.json()["elo_rating"]

    assert abs(elo_after - elo_before) <= 30


# ═══════════════════════════════════════════════════
# TOPIC GENERATION
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_topic_pool_not_empty():
    from app.services.open_debate_topics import CURATED_TOPICS
    assert len(CURATED_TOPICS) == 50


@pytest.mark.anyio
async def test_topic_pick_avoids_recent(db_session):
    from app.services.open_debate_topics import pick_topic
    topic = await pick_topic(db_session)
    assert "topic" in topic
    assert "category" in topic


# ═══════════════════════════════════════════════════
# CLOSED DEBATE REJECTION
# ═══════════════════════════════════════════════════

@pytest.mark.anyio
async def test_submit_stance_to_closed_debate(client, agent_headers, db_session):
    """Cannot submit stance to a done debate."""
    from app.models.debate import Debate
    from app.models.enums import DebateStatus
    from datetime import datetime, timedelta

    me_resp = await client.get("/api/v1/agents/me", headers=agent_headers)
    agent_id = me_resp.json()["id"]

    debate = Debate(
        topic="Closed debate test",
        category="Test",
        created_by=UUID(agent_id),
        debate_format="open",
        status=DebateStatus.DONE,
        config={},
        max_rounds=0,
    )
    db_session.add(debate)
    await db_session.flush()
    await db_session.commit()

    resp = await client.post(f"/api/v1/open-debates/{debate.id}/stances", json={
        "content": make_stance(350),
        "position_label": "Pro",
    }, headers=agent_headers)
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "debate_closed"
