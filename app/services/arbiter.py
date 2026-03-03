import json
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings

PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
)


def load_prompt(filename: str) -> str:
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def interpolate_prompt(template: str, **kwargs) -> str:
    for key, value in kwargs.items():
        placeholder = "{{" + key + "}}"
        if isinstance(value, (dict, list)):
            value = json.dumps(value, indent=2)
        template = template.replace(placeholder, str(value))
    return template


async def call_layer1(prompt: str) -> dict:
    """Call Layer 1 arbiter (DeepSeek V3.2) for structural validation."""
    response = await client.chat.completions.create(
        model=settings.ARBITER_LAYER1_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        max_tokens=2000,
    )
    content = response.choices[0].message.content
    return _parse_json_response(content)


async def call_layer2(prompt: str) -> dict:
    """Call Layer 2 arbiter (Kimi K2.5) for substantive evaluation."""
    response = await client.chat.completions.create(
        model=settings.ARBITER_LAYER2_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=16000,
    )
    content = response.choices[0].message.content
    return _parse_json_response(content)


def _parse_json_response(content: str) -> dict:
    """Parse JSON from arbiter response, handling markdown code blocks."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = lines[1:]  # Remove opening ```json or ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    return json.loads(content)


async def validate_turn(
    debate_topic: str,
    phase_0_structure: dict,
    current_round: int,
    agent_name: str,
    school_of_thought: str,
    must_falsify: bool,
    turn_content: str,
    toulmin_tags: list,
    falsification_target: Optional[dict],
) -> dict:
    """Validate a turn using Layer 1 arbiter."""
    template = load_prompt("layer1_validate_turn.md")
    prompt = interpolate_prompt(
        template,
        debate_topic=debate_topic,
        phase_0_structure_json=phase_0_structure,
        current_round=current_round,
        agent_name=agent_name,
        school_of_thought=school_of_thought or "Not specified",
        must_falsify=str(must_falsify).lower(),
        turn_content=turn_content,
        toulmin_tags_json=toulmin_tags,
        falsification_target_json=falsification_target or "null",
    )
    return await call_layer1(prompt)


async def validate_phase0_declaration(
    debate_topic: str,
    declaration_content: str,
) -> dict:
    """Validate Phase 0 declaration using Layer 1."""
    template = load_prompt("layer1_validate_phase0.md")
    prompt = interpolate_prompt(
        template,
        debate_topic=debate_topic,
        declaration_content=declaration_content,
    )
    return await call_layer1(prompt)


async def generate_default_structure(
    debate_topic: str,
    participants_info: list[dict],
) -> dict:
    """Generate a default Lakatosian structure when Phase 0 deadlocks."""
    template = load_prompt("layer2_default_structure.md")
    prompt = interpolate_prompt(
        template,
        debate_topic=debate_topic,
        participants_json=participants_info,
    )
    return await call_layer2(prompt)


async def evaluate_debate(
    debate_topic: str,
    category: str,
    phase_0_structure: dict,
    participants: list[dict],
    full_transcript: str,
    citation_challenges: list[dict],
    audience_votes_summary: dict,
    relevant_graph_nodes: list[dict],
) -> dict:
    """Full post-debate evaluation using Layer 2."""
    template = load_prompt("layer2_evaluate_debate.md")
    prompt = interpolate_prompt(
        template,
        debate_topic=debate_topic,
        category=category or "Uncategorized",
        phase_0_structure_json=phase_0_structure,
        participants_json=participants,
        full_transcript=full_transcript,
        citation_challenges_json=citation_challenges,
        audience_votes_summary=audience_votes_summary,
        relevant_graph_nodes=relevant_graph_nodes,
    )
    return await call_layer2(prompt)
