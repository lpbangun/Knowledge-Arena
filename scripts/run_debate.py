#!/usr/bin/env python3
"""
Knowledge Arena — 6-Agent Autonomous Debate Runner
===================================================
Stress-tests the live platform by deploying 6 AI agents that debate each other
through the full lifecycle: registration → Phase 0 → active rounds → completion.

Usage:
    export OPENROUTER_API_KEY=sk-or-...
    python scripts/run_debate.py [--base-url URL] [--rounds N]
"""

import argparse
import asyncio
import io
import json
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import httpx
import httpcore
from openai import AsyncOpenAI

# Load .env file if present
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_URL = "https://knowledge-arena.up.railway.app"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MAX_POLL_ATTEMPTS = 30  # max times to poll for validation/round advance
POLL_INTERVAL = 3  # seconds between polls
LLM_TIMEOUT = 120  # seconds for LLM calls

DEBATE_TOPIC = (
    "Does artificial intelligence primarily displace or augment human labor "
    "in knowledge work, and what are the second-order societal consequences?"
)
DEBATE_DESCRIPTION = (
    "A structured 6-agent debate examining AI's impact on white-collar employment, "
    "skill evolution, wage dynamics, and institutional adaptation. Agents represent "
    "diverse epistemological frameworks to stress-test the platform's multi-agent "
    "protocol engine."
)

# ─── Agent Definitions ───────────────────────────────────────────────────────

AGENTS = [
    {
        "name": "Empiricus",
        "model_id": "deepseek/deepseek-v3.2",
        "school": "Empiricism",
        "persona": (
            "You are Empiricus, an empiricist AI debater. You ground every claim in "
            "observable data, statistical evidence, and peer-reviewed studies. You distrust "
            "abstract reasoning divorced from measurement. You believe AI displaces specific "
            "task categories but the net employment effect depends on measurable retraining "
            "capacity and labor market friction coefficients."
        ),
    },
    {
        "name": "Rationalis",
        "model_id": "deepseek/deepseek-v3.2",
        "school": "Rationalism",
        "persona": (
            "You are Rationalis, a rationalist AI debater. You derive conclusions from "
            "first principles, logical deduction, and mathematical models. You believe "
            "economic theory predicts that AI augments human comparative advantage through "
            "task complementarity, and that displacement fears stem from compositional "
            "fallacies in reasoning about aggregate labor demand."
        ),
    },
    {
        "name": "Falsifier",
        "model_id": "deepseek/deepseek-v3.2",
        "school": "Popperian Falsificationism",
        "persona": (
            "You are Falsifier, a Popperian falsificationist AI debater. You seek to "
            "disprove claims rather than confirm them. You challenge every hypothesis with "
            "counter-evidence and demand falsifiable predictions. You argue that most claims "
            "about AI's labor impact are unfalsifiable in their current form and need to be "
            "reformulated with specific, testable predictions."
        ),
    },
    {
        "name": "Dialectron",
        "model_id": "qwen/qwen3.5-35b-a3b",
        "school": "Hegelian Dialectics",
        "persona": (
            "You are Dialectron, a Hegelian dialectician AI debater. You see displacement "
            "and augmentation as thesis and antithesis that must be synthesized into a higher "
            "understanding. You argue that AI transforms the very nature of labor, creating "
            "a qualitative shift that transcends the displacement/augmentation dichotomy. "
            "You seek synthesis from opposing positions."
        ),
    },
    {
        "name": "Pragmatix",
        "model_id": "qwen/qwen3.5-35b-a3b",
        "school": "Pragmatism",
        "persona": (
            "You are Pragmatix, a pragmatist AI debater. You evaluate claims by their "
            "practical consequences and real-world outcomes. You argue that the displacement "
            "vs augmentation question is less important than whether institutional responses "
            "(education, safety nets, regulation) are adequate. You focus on actionable "
            "policy implications rather than abstract theory."
        ),
    },
    {
        "name": "Bayesian",
        "model_id": "qwen/qwen3.5-35b-a3b",
        "school": "Bayesian Epistemology",
        "persona": (
            "You are Bayesian, a Bayesian epistemologist AI debater. You update beliefs "
            "probabilistically based on evidence strength. You assign prior probabilities "
            "to displacement and augmentation hypotheses and update them with each piece of "
            "evidence presented. You argue that the truth lies in a probability distribution "
            "over outcomes, not a binary displacement/augmentation answer."
        ),
    },
]


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class AgentState:
    name: str
    model_id: str
    school: str
    persona: str
    agent_id: str = ""
    api_key: str = ""
    headers: dict = field(default_factory=dict)
    turns_submitted: int = 0
    errors: list = field(default_factory=list)


# ─── Logging ──────────────────────────────────────────────────────────────────

class DebateLogger:
    def __init__(self):
        self.start_time = time.time()
        self.events = []

    def log(self, level: str, msg: str, data: dict = None):
        elapsed = time.time() - self.start_time
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {"INFO": "  ", "OK": "  OK  ", "FAIL": " FAIL ", "WARN": " WARN ", "STEP": ">>>>> "}
        tag = prefix.get(level, "  ")
        print(f"[{timestamp}] [{elapsed:7.1f}s] {tag} {msg}", flush=True)
        if data:
            for k, v in data.items():
                val = str(v)[:200]
                print(f"{'':30}   {k}: {val}", flush=True)
        self.events.append({"time": elapsed, "level": level, "msg": msg, "data": data})

    def info(self, msg, **kw): self.log("INFO", msg, kw if kw else None)
    def ok(self, msg, **kw): self.log("OK", msg, kw if kw else None)
    def fail(self, msg, **kw): self.log("FAIL", msg, kw if kw else None)
    def warn(self, msg, **kw): self.log("WARN", msg, kw if kw else None)
    def step(self, msg): self.log("STEP", msg)

    def summary(self):
        elapsed = time.time() - self.start_time
        oks = sum(1 for e in self.events if e["level"] == "OK")
        fails = sum(1 for e in self.events if e["level"] == "FAIL")
        warns = sum(1 for e in self.events if e["level"] == "WARN")
        print(f"\n{'=' * 70}")
        print(f"  DEBATE RUNNER SUMMARY")
        print(f"  Total time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
        print(f"  Results: {oks} passed, {fails} failed, {warns} warnings")
        print(f"{'=' * 70}")
        if fails:
            print(f"\n  FAILURES:")
            for e in self.events:
                if e["level"] == "FAIL":
                    print(f"    - [{e['time']:.1f}s] {e['msg']}")
                    if e.get("data"):
                        for k, v in e["data"].items():
                            print(f"      {k}: {str(v)[:300]}")
        return fails


log = DebateLogger()


# ─── LLM Client ──────────────────────────────────────────────────────────────

llm_client = None

def get_llm_client():
    global llm_client
    if llm_client is None:
        # Use explicit httpx client with reasonable timeouts
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=15.0, read=90.0, write=15.0, pool=15.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        llm_client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
            http_client=http_client,
        )
    return llm_client


LLM_MAX_RETRIES = 3

async def call_llm(model_id: str, system_prompt: str, user_prompt: str) -> str:
    """Call OpenRouter LLM with retries and return raw text response."""
    client = get_llm_client()
    last_error = None

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=4000,
            )
            content = response.choices[0].message.content
            if content is None:
                # Some reasoning models put content in reasoning field
                msg = response.choices[0].message
                reasoning = getattr(msg, "reasoning", None)
                if reasoning and isinstance(reasoning, str):
                    content = reasoning.split("\n")[-1].strip()
                if not content:
                    content = "[Model returned empty content]"
            return content.strip()
        except Exception as e:
            last_error = e
            if attempt < LLM_MAX_RETRIES:
                wait = 2 ** attempt
                log.warn(f"LLM call failed ({model_id}), retry {attempt}/{LLM_MAX_RETRIES} in {wait}s",
                         error=str(e)[:100])
                await asyncio.sleep(wait)
            else:
                log.fail(f"LLM call failed ({model_id}) after {LLM_MAX_RETRIES} retries", error=str(e))
                raise


async def generate_structured_turn(agent: AgentState, prompt: str) -> dict:
    """Generate a debate turn with proper Toulmin structure via LLM."""
    system = f"""{agent.persona}

You are participating in a structured academic debate on the Knowledge Arena platform.
You MUST respond with ONLY a valid JSON object (no markdown, no code blocks, no explanation).

The JSON must have this exact structure:
{{
    "content": "<your argument text, 300-800 words>",
    "toulmin_tags": [
        {{"type": "claim", "start": 0, "end": <int>, "label": "<description>"}},
        {{"type": "data", "start": <int>, "end": <int>, "label": "<description>"}},
        {{"type": "warrant", "start": <int>, "end": <int>, "label": "<description>"}}
    ],
    "citation_references": [
        {{"source": "<author (year) - title>", "url": "<url or empty string>"}}
    ]
}}

CRITICAL RULES:
- "start" and "end" are character offsets into your "content" string
- "end" MUST be greater than "start"
- "start" must be >= 0
- You MUST include at least 1 claim, 1 data, and 1 warrant tag
- Tags should cover actual text spans in your content
- Keep content between 300-800 words
- Include 1-3 citation references
- Output ONLY the JSON object, nothing else"""

    raw = await call_llm(agent.model_id, system, prompt)

    # Parse JSON — handle markdown code blocks
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    # Also try to find JSON object if there's surrounding text
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        log.warn(f"JSON parse failed for {agent.name}, using fallback", error=str(e), raw=text[:200])
        # Fallback: create a minimal valid turn from the raw text
        content = raw[:2000] if len(raw) > 10 else f"[{agent.name}] argues from a {agent.school} perspective on this topic."
        # Strip any non-content characters
        content = content.replace("```json", "").replace("```", "").strip()
        if len(content) < 20:
            content = f"{agent.name} presents their {agent.school} analysis of AI's impact on labor markets, arguing based on their epistemological framework that the evidence must be carefully examined."
        data = {
            "content": content,
            "toulmin_tags": [
                {"type": "claim", "start": 0, "end": min(80, len(content)), "label": "Main thesis"},
                {"type": "data", "start": min(80, len(content) - 40), "end": min(160, len(content)), "label": "Supporting evidence"},
                {"type": "warrant", "start": min(160, len(content) - 20), "end": len(content), "label": "Reasoning bridge"},
            ],
            "citation_references": [],
        }

    # Validate and fix toulmin tags
    content = data.get("content", "")
    tags = data.get("toulmin_tags", [])
    fixed_tags = []
    for tag in tags:
        start = max(0, int(tag.get("start", 0)))
        end = int(tag.get("end", start + 10))
        if end <= start:
            end = min(start + 50, len(content))
        if end > len(content):
            end = len(content)
        if start >= end:
            start = max(0, end - 50)
        fixed_tags.append({
            "type": tag.get("type", "claim"),
            "start": start,
            "end": end,
            "label": tag.get("label", "Argument element")[:500],
        })

    # Ensure minimum required tags
    tag_types = {t["type"] for t in fixed_tags}
    for required in ["claim", "data", "warrant"]:
        if required not in tag_types:
            chunk = len(content) // 4
            offsets = {"claim": (0, chunk), "data": (chunk, chunk * 2), "warrant": (chunk * 2, chunk * 3)}
            s, e = offsets[required]
            fixed_tags.append({
                "type": required,
                "start": s,
                "end": min(e, len(content)),
                "label": f"Auto-tagged {required}",
            })

    data["toulmin_tags"] = fixed_tags
    data["citation_references"] = data.get("citation_references", [])

    # Fix citation references
    fixed_citations = []
    for cit in data["citation_references"]:
        if isinstance(cit, dict) and "source" in cit:
            fixed_citations.append({
                "source": str(cit["source"])[:500],
                "url": str(cit.get("url", ""))[:2000] or None,
                "excerpt": str(cit.get("excerpt", ""))[:2000] or None,
            })
    data["citation_references"] = fixed_citations

    return data


# ─── API Helpers ──────────────────────────────────────────────────────────────

API_MAX_RETRIES = 3

async def api_call(client: httpx.AsyncClient, method: str, path: str,
                   headers: dict = None, json_data: dict = None,
                   expected_status: list = None,
                   timeout_override: float = None) -> tuple[int, dict]:
    """Make an API call with retries and return (status_code, response_json)."""
    url = f"{BASE_URL}{path}"
    expected = expected_status or [200, 201, 202]

    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            kwargs = {"headers": headers}
            if json_data is not None:
                kwargs["json"] = json_data
            if timeout_override:
                kwargs["timeout"] = timeout_override

            if method == "GET":
                resp = await client.get(url, **kwargs)
            elif method == "POST":
                resp = await client.post(url, **kwargs)
            elif method == "PATCH":
                resp = await client.patch(url, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")

            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text[:500]}

            if resp.status_code not in expected:
                log.fail(f"API {method} {path} -> {resp.status_code}", response=body)

            return resp.status_code, body
        except httpx.TimeoutException:
            if attempt < API_MAX_RETRIES:
                wait = 5 * attempt
                log.warn(f"API timeout: {method} {path}, retry {attempt}/{API_MAX_RETRIES} in {wait}s")
                await asyncio.sleep(wait)
            else:
                log.fail(f"API timeout after {API_MAX_RETRIES} retries: {method} {path}")
                return 0, {"error": "timeout"}
        except Exception as e:
            if attempt < API_MAX_RETRIES:
                wait = 3 * attempt
                log.warn(f"API error: {method} {path}, retry {attempt}", error=str(e)[:80])
                await asyncio.sleep(wait)
            else:
                log.fail(f"API error after retries: {method} {path}", error=str(e))
                return 0, {"error": str(e)}
    return 0, {"error": "exhausted retries"}


# ─── Debate Runner ────────────────────────────────────────────────────────────

async def run_debate(max_rounds: int = 8):
    """Run a full 6-agent debate lifecycle."""

    agents: list[AgentState] = []
    debate_id = None

    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=15.0, read=120.0, write=15.0, pool=15.0)) as client:

        # ─── Step 0: Health Check ─────────────────────────────────────────
        log.step("HEALTH CHECK")
        status, body = await api_call(client, "GET", "/health")
        if status == 200:
            log.ok(f"Server healthy: {body}")
        else:
            log.fail("Server unreachable — aborting")
            return

        # ─── Step 1: Register All 6 Agents ───────────────────────────────
        log.step("REGISTERING 6 AGENTS")
        timestamp = int(time.time())

        for i, agent_def in enumerate(AGENTS):
            unique_name = f"{agent_def['name']}_{timestamp}"
            email = f"{agent_def['name'].lower()}_{timestamp}@stresstest.dev"

            status, body = await api_call(client, "POST", "/api/v1/agents/register", json_data={
                "name": unique_name,
                "owner_email": email,
                "owner_password": f"stresstest_{timestamp}!",
                "owner_display_name": f"{agent_def['name']} Owner",
                "model_info": {"model_name": agent_def["model_id"], "provider": "openrouter"},
                "school_of_thought": agent_def["school"],
            })

            if status == 201:
                agent = AgentState(
                    name=unique_name,
                    model_id=agent_def["model_id"],
                    school=agent_def["school"],
                    persona=agent_def["persona"],
                    agent_id=body["id"],
                    api_key=body["api_key"],
                    headers={"X-API-Key": body["api_key"]},
                )
                agents.append(agent)
                log.ok(f"Registered {unique_name} (id={body['id'][:8]}...)")
            else:
                log.fail(f"Failed to register {agent_def['name']}", response=body)
                return

        # ─── Step 2: Agent 1 Creates Debate ───────────────────────────────
        log.step("CREATING DEBATE")
        status, body = await api_call(client, "POST", "/api/v1/debates",
            headers=agents[0].headers,
            json_data={
                "topic": DEBATE_TOPIC,
                "description": DEBATE_DESCRIPTION,
                "category": "AI & Labor Economics",
                "config": {"max_agents": 6},
                "max_rounds": max_rounds,
            })

        if status == 201:
            debate_id = body["id"]
            log.ok(f"Debate created: {debate_id[:12]}...", topic=DEBATE_TOPIC[:60])
        else:
            log.fail("Failed to create debate", response=body)
            return

        # ─── Step 3: Agents 2-6 Join ─────────────────────────────────────
        log.step("AGENTS JOINING DEBATE")
        for agent in agents[1:]:
            status, body = await api_call(client, "POST",
                f"/api/v1/debates/{debate_id}/join",
                headers=agent.headers,
                json_data={"role": "debater"})
            if status == 201:
                log.ok(f"{agent.name} joined as debater")
            else:
                log.fail(f"{agent.name} failed to join", response=body)
                return

        # ─── Step 4: Phase 0 — Lakatosian Declarations ───────────────────
        log.step("PHASE 0: LAKATOSIAN DECLARATIONS (parallel)")

        async def generate_and_submit_declaration(agent: AgentState, stagger: float = 0):
            if stagger > 0:
                await asyncio.sleep(stagger)
            log.info(f"Generating declaration for {agent.name} via {agent.model_id}...")
            prompt = f"""You are entering a structured academic debate.
Topic: {DEBATE_TOPIC}

You must declare your Lakatosian research programme structure. Include:
1. Your HARD CORE thesis (your central, unfalsifiable commitment on this topic)
2. Your AUXILIARY HYPOTHESES (testable protective belt propositions, 2-3 items)
3. Your FALSIFICATION CRITERIA (what evidence would make you concede your position)

Write this as a cohesive 200-400 word declaration from your {agent.school} perspective.
Do NOT wrap your response in any JSON or code blocks. Just write the declaration as plain text."""

            try:
                declaration_content = await call_llm(agent.model_id, agent.persona, prompt)

                status, body = await api_call(client, "POST",
                    f"/api/v1/debates/{debate_id}/turns",
                    headers=agent.headers,
                    json_data={
                        "content": declaration_content,
                        "turn_type": "phase_0_declaration",
                        "toulmin_tags": [
                            {"type": "claim", "start": 0, "end": min(100, len(declaration_content)),
                             "label": f"{agent.school} hard core thesis"},
                        ],
                    })
                if status == 202:
                    log.ok(f"{agent.name} declaration submitted ({len(declaration_content)} chars)")
                else:
                    log.fail(f"{agent.name} declaration rejected", response=body)
                    agent.errors.append(f"Declaration rejected: {body}")
            except Exception as e:
                log.fail(f"{agent.name} declaration error", error=str(e))
                agent.errors.append(str(e))

        # Stagger submissions by 1s each to avoid overwhelming the server
        await asyncio.gather(*[generate_and_submit_declaration(a, i * 1.0) for i, a in enumerate(agents)])

        # Wait for all Phase 0 declarations to be validated
        log.info("Waiting for Phase 0 declarations to be validated by arbiter...")
        await _wait_for_phase_transition(client, agents[0], debate_id,
                                          target_check=lambda d: d.get("current_round", 0) >= 1,
                                          description="declarations validated")

        # ─── Step 5: Phase 0 — Negotiation (accept structure) ────────────
        log.step("PHASE 0: NEGOTIATION (accepting structure)")

        # Check current debate state
        status, debate_data = await api_call(client, "GET", f"/api/v1/debates/{debate_id}")
        log.info(f"Debate status: {debate_data.get('status')}, round: {debate_data.get('current_round')}")

        if debate_data.get("status") == "phase_0":
            async def submit_negotiation(agent: AgentState):
                negotiation_content = (
                    f"I, {agent.name}, representing the {agent.school} tradition, "
                    f"accept the proposed debate structure. I acknowledge the Lakatosian "
                    f"framework declarations from all participants and agree to proceed "
                    f"with the structured argumentation phase. I accept these terms and "
                    f"am ready to engage in substantive debate."
                )
                status, body = await api_call(client, "POST",
                    f"/api/v1/debates/{debate_id}/turns",
                    headers=agent.headers,
                    json_data={
                        "content": negotiation_content,
                        "turn_type": "phase_0_negotiation",
                        "toulmin_tags": [],
                    })
                if status == 202:
                    log.ok(f"{agent.name} negotiation submitted (accepts structure)")
                else:
                    log.fail(f"{agent.name} negotiation failed", response=body)

            # Stagger negotiation submissions
            async def staggered_negotiation(agent, delay):
                await asyncio.sleep(delay)
                await submit_negotiation(agent)
            await asyncio.gather(*[staggered_negotiation(a, i * 2.0) for i, a in enumerate(agents)])

            # Wait for transition to ACTIVE
            log.info("Waiting for debate to transition to ACTIVE...")
            await _wait_for_phase_transition(client, agents[0], debate_id,
                                              target_check=lambda d: d.get("status") == "active",
                                              description="debate activated")
        else:
            log.info(f"Debate already past Phase 0 (status={debate_data.get('status')})")

        # ─── Step 6: Active Debate Rounds ─────────────────────────────────
        log.step(f"ACTIVE DEBATE: Running up to {max_rounds} rounds")

        round_num = 0
        while round_num < max_rounds:
            # Check debate status
            status, debate_data = await api_call(client, "GET", f"/api/v1/debates/{debate_id}")
            current_status = debate_data.get("status", "unknown")
            current_round = debate_data.get("current_round", 0)

            if current_status in ("completed", "done", "evaluation", "synthesis", "evaluation_failed"):
                log.ok(f"Debate ended with status: {current_status} at round {current_round}")
                break

            if current_status != "active":
                log.warn(f"Unexpected debate status: {current_status}, waiting...")
                await asyncio.sleep(POLL_INTERVAL)
                continue

            round_num = current_round
            log.step(f"ROUND {round_num}")

            # Get all previous turns for context
            _, turns_data = await api_call(client, "GET",
                f"/api/v1/debates/{debate_id}/turns?limit=100")
            previous_turns = turns_data.get("items", [])

            # Format debate history for agents
            history_text = _format_debate_history(previous_turns, agents)

            # Each agent generates and submits a turn (in parallel)
            async def generate_and_submit_round_turn(agent: AgentState, rn: int, ht: str):
                # Check if this agent needs to submit
                _, status_data = await api_call(client, "GET",
                    f"/api/v1/debates/{debate_id}/status",
                    headers=agent.headers)

                control = status_data.get("control_plane", {})
                action = control.get("action_needed", "")

                if action == "wait":
                    log.info(f"{agent.name} already submitted round {rn}, waiting")
                    return
                elif action == "debate_complete":
                    log.info(f"{agent.name} sees debate as complete")
                    return
                elif action not in ("submit_turn", "resubmit"):
                    log.warn(f"{agent.name} unexpected action: {action}")
                    return

                log.info(f"Generating argument for {agent.name} (round {rn})...")

                prompt = f"""The debate topic is: {DEBATE_TOPIC}

Current round: {rn} of {max_rounds}
Your school of thought: {agent.school}

{ht}

{"This is the opening round. Present your strongest initial argument." if rn <= 1 else f"Respond to the arguments above. Challenge weak points. Strengthen your position. Round {rn} of {max_rounds}."}

{"IMPORTANT: You MUST include a falsification_target - pick one opponent's claim to directly challenge and attempt to falsify." if rn >= 2 and rn % 2 == 0 else ""}

Generate your argument now."""

                try:
                    turn_data = await generate_structured_turn(agent, prompt)

                    payload = {
                        "content": turn_data["content"],
                        "turn_type": "resubmission" if action == "resubmit" else "argument",
                        "toulmin_tags": turn_data["toulmin_tags"],
                        "citation_references": turn_data.get("citation_references", []),
                    }

                    status, body = await api_call(client, "POST",
                        f"/api/v1/debates/{debate_id}/turns",
                        headers=agent.headers,
                        json_data=payload)

                    if status == 202:
                        agent.turns_submitted += 1
                        log.ok(f"{agent.name} turn submitted (round {rn}, "
                               f"{len(turn_data['content'])} chars, "
                               f"{len(turn_data['toulmin_tags'])} tags)")
                    else:
                        log.fail(f"{agent.name} turn rejected", response=body)
                        agent.errors.append(f"Round {rn}: {body}")

                except Exception as e:
                    log.fail(f"{agent.name} turn generation error", error=str(e))
                    agent.errors.append(f"Round {rn}: {str(e)}")

            await asyncio.gather(*[
                generate_and_submit_round_turn(a, round_num, history_text)
                for a in agents
            ])

            # Wait for server-side round advance retries (up to 3s), then check for failed agents
            await asyncio.sleep(5)

            # Wait for all turns to be validated and round to advance
            log.info(f"Waiting for round {round_num} validation and advancement...")
            advanced = await _wait_for_round_advance(client, agents[0], debate_id, round_num)
            if not advanced:
                log.warn(f"Round {round_num} did not advance after polling — checking status")
                _, check = await api_call(client, "GET", f"/api/v1/debates/{debate_id}")
                if check.get("status") in ("completed", "done"):
                    log.ok("Debate completed during round")
                    break
                # Try continuing anyway
                continue

        # ─── Step 7: Post-Debate Results ──────────────────────────────────
        log.step("POST-DEBATE: Collecting results")

        # Final debate status
        _, final_debate = await api_call(client, "GET", f"/api/v1/debates/{debate_id}")
        log.info(f"Final debate status: {final_debate.get('status')}")
        log.info(f"Final round: {final_debate.get('current_round')}")
        log.info(f"Convergence signals: {final_debate.get('convergence_signals')}")

        # Wait briefly for evaluation (Celery may not be running)
        if final_debate.get("status") in ("completed", "evaluation", "synthesis"):
            log.info("Waiting for post-debate evaluation (up to 30s)...")
            for attempt in range(6):
                await asyncio.sleep(5)
                _, check = await api_call(client, "GET", f"/api/v1/debates/{debate_id}")
                if check.get("status") == "done":
                    log.ok("Evaluation complete — debate is DONE")
                    break
                elif check.get("status") == "evaluation_failed":
                    log.warn("Evaluation failed")
                    break
            else:
                log.warn("Evaluation did not complete (Celery/arbiter likely unavailable)")

        # Fetch evaluation results
        _, eval_data = await api_call(client, "GET",
            f"/api/v1/debates/{debate_id}/evaluation", expected_status=[200, 404])
        if eval_data.get("evaluations"):
            log.ok("Evaluation results retrieved")
            for ev in eval_data["evaluations"]:
                agent_id = ev.get("agent_id", "?")
                name = next((a.name for a in agents if a.agent_id == agent_id), agent_id[:8])
                log.info(f"  {name}: composite={ev.get('composite_score', '?'):.2f}, "
                         f"elo={ev.get('elo_before')}→{ev.get('elo_after')}")
        else:
            log.warn("No evaluation results available", data=eval_data)

        # Agent final states
        log.step("AGENT FINAL STATES")
        for agent in agents:
            _, profile = await api_call(client, "GET", f"/api/v1/agents/{agent.agent_id}")
            log.info(f"  {agent.name}: elo={profile.get('elo_rating', '?')}, "
                     f"turns={agent.turns_submitted}, errors={len(agent.errors)}")

        # Check knowledge graph
        _, nodes = await api_call(client, "GET", "/api/v1/graph/nodes")
        _, edges = await api_call(client, "GET", "/api/v1/graph/edges")
        log.info(f"Knowledge graph: {len(nodes.get('items', nodes) if isinstance(nodes, dict) else [])} nodes, "
                 f"{len(edges.get('items', edges) if isinstance(edges, dict) else [])} edges")

    return debate_id


async def _wait_for_phase_transition(client: httpx.AsyncClient, agent: AgentState,
                                      debate_id: str, target_check, description: str) -> bool:
    """Poll debate status until a condition is met."""
    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL)
        status, data = await api_call(client, "GET", f"/api/v1/debates/{debate_id}")
        if status == 200 and target_check(data):
            log.ok(f"Phase transition: {description} (attempt {attempt + 1})")
            return True
        if attempt % 5 == 0:
            log.info(f"  Waiting for {description}... "
                     f"(status={data.get('status')}, round={data.get('current_round')}, "
                     f"attempt {attempt + 1}/{MAX_POLL_ATTEMPTS})")
    log.warn(f"Timeout waiting for: {description}")
    return False


async def _wait_for_round_advance(client: httpx.AsyncClient, agent: AgentState,
                                    debate_id: str, current_round: int) -> bool:
    """Wait for the round to advance past current_round."""
    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL)
        status, data = await api_call(client, "GET", f"/api/v1/debates/{debate_id}")
        if status != 200:
            continue
        new_round = data.get("current_round", 0)
        new_status = data.get("status", "")

        if new_round > current_round:
            log.ok(f"Round advanced: {current_round} → {new_round}")
            return True
        if new_status in ("completed", "done", "evaluation", "synthesis", "evaluation_failed"):
            log.ok(f"Debate ended during round {current_round} (status={new_status})")
            return True
        if attempt % 5 == 0:
            log.info(f"  Waiting for round advance... "
                     f"(round={new_round}, status={new_status}, attempt {attempt + 1})")
    return False


def _format_debate_history(turns: list[dict], agents: list[AgentState]) -> str:
    """Format previous turns into readable context for LLM."""
    if not turns:
        return "No previous arguments have been made yet."

    agent_names = {a.agent_id: a.name for a in agents}
    lines = ["=== Previous Arguments ==="]
    for t in turns[-18:]:  # Last 18 turns (3 rounds × 6 agents)
        agent_id = t.get("agent_id", "")
        name = agent_names.get(agent_id, agent_id[:8])
        round_n = t.get("round_number", "?")
        content = t.get("content", "")[:600]
        turn_type = t.get("turn_type", "argument")
        if turn_type in ("phase_0_declaration", "phase_0_negotiation"):
            continue
        lines.append(f"\n[Round {round_n}] {name}:\n{content}")
    return "\n".join(lines) if len(lines) > 1 else "No substantive arguments yet."


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    global BASE_URL
    parser = argparse.ArgumentParser(description="Knowledge Arena 6-Agent Debate Runner")
    parser.add_argument("--base-url", default=BASE_URL, help="API base URL")
    parser.add_argument("--rounds", type=int, default=8, help="Max debate rounds")
    args = parser.parse_args()

    BASE_URL = args.base_url

    if not OPENROUTER_API_KEY:
        print("ERROR: Set OPENROUTER_API_KEY environment variable")
        sys.exit(1)

    print(f"\n{'=' * 70}")
    print(f"  KNOWLEDGE ARENA — 6-AGENT STRESS TEST")
    print(f"  Target: {BASE_URL}")
    print(f"  Rounds: {args.rounds}")
    print(f"  Models: 3× deepseek/deepseek-v3.2 + 3× qwen/qwen3.5-35b-a3b")
    print(f"  Topic:  {DEBATE_TOPIC[:60]}...")
    print(f"{'=' * 70}\n")

    try:
        debate_id = await run_debate(max_rounds=args.rounds)
        if debate_id:
            print(f"\n  Debate URL: {BASE_URL}/debates/{debate_id}")
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except Exception as e:
        log.fail(f"Fatal error: {e}")
        traceback.print_exc()

    fails = log.summary()
    sys.exit(1 if fails > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
