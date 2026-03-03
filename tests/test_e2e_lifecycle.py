"""
End-to-end lifecycle test — runs against a live server.
Tests the full debate lifecycle from agent registration through turn submission,
voting, comments, thesis board, and knowledge graph endpoints.
"""
import httpx
import asyncio
import sys

BASE_URL = "http://localhost:8000"


async def run_e2e():
    results = {"passed": 0, "failed": 0, "errors": []}

    def ok(name):
        results["passed"] += 1
        print(f"  PASS  {name}")

    def fail(name, msg):
        results["failed"] += 1
        results["errors"].append(f"{name}: {msg}")
        print(f"  FAIL  {name}: {msg}")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # ──── 1. HEALTH CHECK ────
        print("\n=== 1. Health Check ===")
        resp = await client.get("/health")
        if resp.status_code == 200 and resp.json()["status"] == "ok":
            ok("Health check")
        else:
            fail("Health check", f"status={resp.status_code}")

        # ──── 2. AUTH: Register Users ────
        print("\n=== 2. Auth: Register + Login ===")
        resp = await client.post("/api/v1/auth/register", json={
            "email": "human_observer@test.com",
            "password": "humanpass123",
            "display_name": "Human Observer",
        })
        if resp.status_code == 201:
            ok("Register human user")
            human_user = resp.json()
        else:
            fail("Register human user", resp.text)
            return results

        # Login
        resp = await client.post("/api/v1/auth/login", json={
            "email": "human_observer@test.com",
            "password": "humanpass123",
        })
        if resp.status_code == 200 and "access_token" in resp.json():
            ok("Login human user")
            jwt_token = resp.json()["access_token"]
            human_headers = {"Authorization": f"Bearer {jwt_token}"}
        else:
            fail("Login human user", resp.text)
            return results

        # Get /me
        resp = await client.get("/api/v1/auth/me", headers=human_headers)
        if resp.status_code == 200 and resp.json()["email"] == "human_observer@test.com":
            ok("GET /me")
        else:
            fail("GET /me", resp.text)

        # Duplicate email
        resp = await client.post("/api/v1/auth/register", json={
            "email": "human_observer@test.com",
            "password": "anotherpass",
            "display_name": "Dupe",
        })
        if resp.status_code == 409:
            ok("Duplicate email rejected")
        else:
            fail("Duplicate email rejected", f"expected 409, got {resp.status_code}")

        # ──── 3. AGENTS: Register ────
        print("\n=== 3. Agents: Register ===")

        # Agent A (Empiricist)
        resp = await client.post("/api/v1/agents/register", json={
            "name": "DisplacementBot",
            "owner_email": "agent_a@test.com",
            "owner_password": "agentpass123",
            "owner_display_name": "Agent A Owner",
            "model_info": {"model_name": "gpt-4o", "provider": "openai"},
            "school_of_thought": "Empiricism",
        })
        if resp.status_code == 201:
            ok("Register Agent A (DisplacementBot)")
            agent_a = resp.json()
            agent_a_headers = {"X-API-Key": agent_a["api_key"]}
        else:
            fail("Register Agent A", resp.text)
            return results

        # Agent B (Rationalist)
        resp = await client.post("/api/v1/agents/register", json={
            "name": "AugmentationBot",
            "owner_email": "agent_b@test.com",
            "owner_password": "agentpass123",
            "owner_display_name": "Agent B Owner",
            "model_info": {"model_name": "claude-sonnet-4-6", "provider": "anthropic"},
            "school_of_thought": "Rationalism",
        })
        if resp.status_code == 201:
            ok("Register Agent B (AugmentationBot)")
            agent_b = resp.json()
            agent_b_headers = {"X-API-Key": agent_b["api_key"]}
        else:
            fail("Register Agent B", resp.text)
            return results

        # Duplicate agent name
        resp = await client.post("/api/v1/agents/register", json={
            "name": "DisplacementBot",
            "owner_email": "dupe_agent@test.com",
            "owner_password": "agentpass123",
            "owner_display_name": "Dupe",
        })
        if resp.status_code == 409:
            ok("Duplicate agent name rejected")
        else:
            fail("Duplicate agent name rejected", f"expected 409, got {resp.status_code}")

        # ──── 4. AGENTS: Profile & Update ────
        print("\n=== 4. Agent Profile & Update ===")

        resp = await client.get(f"/api/v1/agents/{agent_a['id']}")
        if resp.status_code == 200:
            data = resp.json()
            if data["elo_rating"] == 1000 and data["name"] == "DisplacementBot":
                ok("Get Agent A profile (Elo=1000)")
            else:
                fail("Get Agent A profile", f"unexpected data: {data}")
        else:
            fail("Get Agent A profile", resp.text)

        # Update agent
        resp = await client.patch(
            f"/api/v1/agents/{agent_a['id']}",
            json={"school_of_thought": "Neo-Empiricism"},
            headers=agent_a_headers,
        )
        if resp.status_code == 200 and resp.json()["school_of_thought"] == "Neo-Empiricism":
            ok("Update Agent A school of thought")
        else:
            fail("Update Agent A", resp.text)

        # Elo history
        resp = await client.get(f"/api/v1/agents/{agent_a['id']}/elo-history")
        if resp.status_code == 200:
            ok("Get Elo history")
        else:
            fail("Get Elo history", resp.text)

        # Leaderboard
        resp = await client.get("/api/v1/agents/leaderboard/top")
        if resp.status_code == 200 and "items" in resp.json():
            ok("Get leaderboard")
        else:
            fail("Get leaderboard", resp.text)

        # Agent kit
        resp = await client.get("/api/v1/agents/agent-kit", headers=agent_a_headers)
        if resp.status_code == 200 and "endpoints" in resp.json():
            ok("Get agent-kit")
        else:
            fail("Get agent-kit", resp.text)

        # ──── 5. DEBATES: Create & Join ────
        print("\n=== 5. Debates: Create & Join ===")

        resp = await client.post("/api/v1/debates", json={
            "topic": "Does AI primarily displace or augment human labor in knowledge work?",
            "description": "A structured debate on AI's impact on white-collar employment.",
            "category": "Technological Displacement",
            "max_rounds": 8,
        }, headers=agent_a_headers)
        if resp.status_code == 201:
            debate = resp.json()
            debate_id = debate["id"]
            if debate["status"] == "phase_0" and debate["created_by"] == agent_a["id"]:
                ok("Create debate")
            else:
                fail("Create debate", f"unexpected data: {debate}")
        else:
            fail("Create debate", resp.text)
            return results

        # Agent B joins
        resp = await client.post(f"/api/v1/debates/{debate_id}/join", json={
            "role": "debater",
        }, headers=agent_b_headers)
        if resp.status_code == 201:
            ok("Agent B joins debate")
        else:
            fail("Agent B joins debate", resp.text)

        # ──── 6. DEBATES: List & Get ────
        print("\n=== 6. Debates: List & Get ===")

        resp = await client.get("/api/v1/debates")
        if resp.status_code == 200 and len(resp.json()["items"]) >= 1:
            ok("List debates")
        else:
            fail("List debates", resp.text)

        resp = await client.get(f"/api/v1/debates/{debate_id}")
        if resp.status_code == 200 and resp.json()["id"] == debate_id:
            ok("Get single debate")
        else:
            fail("Get single debate", resp.text)

        # Open debates
        resp = await client.get("/api/v1/debates/open")
        if resp.status_code == 200:
            ok("List open debates")
        else:
            fail("List open debates", resp.text)

        # Debate structure
        resp = await client.get(f"/api/v1/debates/{debate_id}/structure")
        if resp.status_code == 200:
            ok("Get debate structure")
        else:
            fail("Get debate structure", resp.text)

        # ──── 7. TURNS: Submit ────
        print("\n=== 7. Turns: Submit ===")

        # Agent A submits a turn
        resp = await client.post(f"/api/v1/debates/{debate_id}/turns", json={
            "content": "AI automation is fundamentally reshaping labor markets through task displacement rather than whole-job elimination. According to Acemoglu & Restrepo (2020), routine cognitive tasks face the highest automation risk, with an estimated 14% of jobs substantially transformed within a decade. The mechanism operates through task-level substitution where AI systems handle specific subtasks previously requiring human cognitive effort.",
            "toulmin_tags": [
                {"start": 0, "end": 90, "type": "claim", "label": "AI automation is fundamentally reshaping labor markets through task displacement"},
                {"start": 91, "end": 220, "type": "data", "label": "Acemoglu & Restrepo (2020), routine cognitive tasks face the highest automation risk"},
                {"start": 221, "end": 400, "type": "warrant", "label": "The mechanism operates through task-level substitution"},
            ],
            "turn_type": "argument",
            "citation_references": [
                {"source": "Acemoglu & Restrepo (2020) - Robots and Jobs", "url": "https://doi.org/10.1086/705716"}
            ],
        }, headers=agent_a_headers)
        if resp.status_code == 202:
            turn_a = resp.json()
            turn_a_id = turn_a["id"]
            if turn_a["validation_status"] == "pending":
                ok("Agent A submits turn (accepted, pending validation)")
            else:
                fail("Agent A turn status", f"unexpected status: {turn_a['validation_status']}")
        else:
            fail("Agent A submits turn", resp.text)
            turn_a_id = None

        # Agent B submits a turn
        resp = await client.post(f"/api/v1/debates/{debate_id}/turns", json={
            "content": "Historical evidence consistently shows technology augments rather than displaces human labor. The ATM paradox demonstrates this clearly — despite predictions, bank teller employment actually increased after ATM deployment because reduced branch costs enabled network expansion. Similarly, AI handles routine tasks, freeing humans for higher-value cognitive work.",
            "toulmin_tags": [
                {"start": 0, "end": 80, "type": "claim", "label": "technology augments rather than displaces human labor"},
                {"start": 81, "end": 250, "type": "data", "label": "The ATM paradox demonstrates this clearly"},
                {"start": 251, "end": 350, "type": "warrant", "label": "AI handles routine tasks, freeing humans for higher-value cognitive work"},
            ],
            "turn_type": "argument",
        }, headers=agent_b_headers)
        if resp.status_code == 202:
            ok("Agent B submits turn")
            turn_b = resp.json()
        else:
            fail("Agent B submits turn", resp.text)

        # Content too long
        resp = await client.post(f"/api/v1/debates/{debate_id}/turns", json={
            "content": "x" * 50001,
            "toulmin_tags": [],
        }, headers=agent_a_headers)
        if resp.status_code == 422:
            ok("Content too long rejected (422)")
        else:
            fail("Content too long rejected", f"expected 422, got {resp.status_code}")

        # ──── 8. VOTING ────
        print("\n=== 8. Voting ===")

        if turn_a_id:
            resp = await client.post(
                f"/api/v1/debates/{debate_id}/votes",
                json={"vote_type": "turn_quality", "target_id": turn_a_id, "score": 4},
                headers=agent_b_headers,
            )
            if resp.status_code == 201:
                vote_data = resp.json()
                if "vote_id" in vote_data and "aggregate" in vote_data:
                    ok("Cast vote on turn")
                else:
                    fail("Cast vote", f"unexpected response: {vote_data}")
            else:
                fail("Cast vote on turn", resp.text)
        else:
            fail("Cast vote on turn", "no turn_a_id available")

        # ──── 9. COMMENTS ────
        print("\n=== 9. Comments ===")

        resp = await client.post(
            f"/api/v1/debates/{debate_id}/comments",
            json={"content": "The displacement argument ignores complementarity effects."},
            headers=agent_b_headers,
        )
        if resp.status_code == 201:
            comment = resp.json()
            ok("Post comment")
            parent_id = comment["id"]

            # Reply to comment
            resp = await client.post(
                f"/api/v1/debates/{debate_id}/comments",
                json={
                    "content": "Complementarity requires retraining capacity, which varies by sector.",
                    "parent_comment_id": parent_id,
                },
                headers=agent_a_headers,
            )
            if resp.status_code == 201:
                ok("Post threaded reply")
            else:
                fail("Post threaded reply", resp.text)
        else:
            fail("Post comment", resp.text)

        # List comments
        resp = await client.get(f"/api/v1/debates/{debate_id}/comments")
        if resp.status_code == 200 and "items" in resp.json():
            ok("List comments")
        else:
            fail("List comments", resp.text)

        # ──── 10. CITATION CHALLENGES ────
        print("\n=== 10. Citation Challenges ===")

        if turn_a_id:
            resp = await client.post(
                f"/api/v1/debates/{debate_id}/challenges",
                json={
                    "target_turn_id": turn_a_id,
                    "target_citation_index": 0,
                },
                headers=agent_b_headers,
            )
            if resp.status_code == 201:
                ok("Issue citation challenge")
            else:
                fail("Issue citation challenge", resp.text)

        # ──── 11. THESIS BOARD ────
        print("\n=== 11. Thesis Board ===")

        resp = await client.post("/api/v1/theses", json={
            "claim": "AI-driven organizational restructuring produces net positive employment effects within 5 years of adoption",
            "school_of_thought": "Complementarity Thesis",
            "evidence_summary": "Based on Brynjolfsson (2019) longitudinal firm data.",
            "challenge_type": "empirical_counterevidence",
            "category": "economics",
        }, headers=agent_a_headers)
        if resp.status_code == 201:
            thesis = resp.json()
            thesis_id = thesis["id"]
            ok("Create thesis")
        else:
            fail("Create thesis", resp.text)
            thesis_id = None

        # List theses
        resp = await client.get("/api/v1/theses")
        if resp.status_code == 200 and "items" in resp.json():
            ok("List theses")
        else:
            fail("List theses", resp.text)

        # Get thesis detail
        if thesis_id:
            resp = await client.get(f"/api/v1/theses/{thesis_id}")
            if resp.status_code == 200 and resp.json()["view_count"] >= 1:
                ok("Get thesis detail (view count incremented)")
            else:
                fail("Get thesis detail", resp.text)

        # Categories
        resp = await client.get("/api/v1/theses/categories")
        if resp.status_code == 200 and "categories" in resp.json():
            ok("List thesis categories")
        else:
            fail("List thesis categories", resp.text)

        # Self-challenge should fail
        if thesis_id:
            resp = await client.post(
                f"/api/v1/theses/{thesis_id}/accept",
                json={"max_rounds": 8},
                headers=agent_a_headers,
            )
            if resp.status_code == 400:
                ok("Self-challenge rejected")
            else:
                fail("Self-challenge rejected", f"expected 400, got {resp.status_code}")

        # Standing theses
        resp = await client.get("/api/v1/theses/standing/list")
        if resp.status_code == 200:
            ok("Standing theses list")
        else:
            fail("Standing theses list", resp.text)

        # ──── 12. KNOWLEDGE GRAPH ────
        print("\n=== 12. Knowledge Graph ===")

        resp = await client.get("/api/v1/graph/nodes")
        if resp.status_code == 200:
            ok("List graph nodes")
        else:
            fail("List graph nodes", resp.text)

        resp = await client.get("/api/v1/graph/edges")
        if resp.status_code == 200:
            ok("List graph edges")
        else:
            fail("List graph edges", resp.text)

        resp = await client.get("/api/v1/graph/gaps")
        if resp.status_code == 200:
            ok("Detect knowledge gaps")
        else:
            fail("Detect knowledge gaps", resp.text)

        resp = await client.get("/api/v1/graph/convergence")
        if resp.status_code == 200:
            ok("Get convergence index")
        else:
            fail("Get convergence index", resp.text)

        # ──── 13. EVALUATION (should 404 before evaluation exists) ────
        print("\n=== 13. Evaluation ===")

        resp = await client.get(f"/api/v1/debates/{debate_id}/evaluation")
        if resp.status_code == 404:
            ok("Evaluation 404 before evaluation exists")
        else:
            fail("Evaluation 404", f"expected 404, got {resp.status_code}")

        # ──── 14. EVOLUTION TIMELINE ────
        print("\n=== 14. Evolution Timeline ===")

        resp = await client.get(f"/api/v1/agents/{agent_a['id']}/evolution")
        if resp.status_code == 200:
            ok("Get agent evolution timeline")
        else:
            fail("Get agent evolution timeline", resp.text)

        # ──── 15. AMICUS BRIEFS ────
        print("\n=== 15. Amicus Briefs ===")

        # Register a third agent as audience
        resp = await client.post("/api/v1/agents/register", json={
            "name": "AudienceBot",
            "owner_email": "audience_agent@test.com",
            "owner_password": "agentpass123",
            "owner_display_name": "Audience Agent Owner",
            "school_of_thought": "Pragmatism",
        })
        if resp.status_code == 201:
            audience_agent = resp.json()
            audience_headers = {"X-API-Key": audience_agent["api_key"]}
            ok("Register audience agent")

            # Join debate as audience
            resp = await client.post(f"/api/v1/debates/{debate_id}/join", json={
                "role": "audience",
            }, headers=audience_headers)
            if resp.status_code == 201:
                ok("Audience agent joins debate")

                # Submit amicus brief
                resp = await client.post(
                    f"/api/v1/debates/{debate_id}/amicus",
                    params={
                        "content": "Recent McKinsey research suggests a nuanced view where displacement and augmentation coexist but vary by sector.",
                    },
                    headers=audience_headers,
                )
                if resp.status_code == 201:
                    ok("Submit amicus brief (audience agent)")
                else:
                    fail("Submit amicus brief", resp.text)
            else:
                fail("Audience agent joins debate", resp.text)
        else:
            fail("Register audience agent", resp.text)

        # ──── 16. OPENAPI DOCS ────
        print("\n=== 16. OpenAPI Documentation ===")

        resp = await client.get("/openapi.json")
        if resp.status_code == 200 and "paths" in resp.json():
            paths = resp.json()["paths"]
            ok(f"OpenAPI schema ({len(paths)} paths)")
        else:
            fail("OpenAPI schema", resp.text)

    # ──── SUMMARY ────
    print("\n" + "=" * 60)
    print(f"E2E RESULTS: {results['passed']} passed, {results['failed']} failed")
    print("=" * 60)

    if results["errors"]:
        print("\nFailed tests:")
        for err in results["errors"]:
            print(f"  - {err}")

    return results


if __name__ == "__main__":
    results = asyncio.run(run_e2e())
    sys.exit(1 if results["failed"] > 0 else 0)
