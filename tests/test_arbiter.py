"""Tests for the arbiter service — Layer 1 validation and Layer 2 evaluation."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.arbiter import (
    _parse_json_response,
    call_layer1,
    call_layer2,
    validate_turn,
    validate_phase0_declaration,
    evaluate_debate,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "arbiter_responses"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def make_mock_response(content: dict) -> MagicMock:
    """Build a mock OpenAI ChatCompletion response."""
    msg = MagicMock()
    msg.content = json.dumps(content)
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ---------- _parse_json_response ----------

class TestParseJsonResponse:
    def test_plain_json(self):
        raw = '{"validation_status": "approved"}'
        assert _parse_json_response(raw) == {"validation_status": "approved"}

    def test_markdown_code_block(self):
        raw = '```json\n{"validation_status": "rejected"}\n```'
        assert _parse_json_response(raw) == {"validation_status": "rejected"}

    def test_code_block_no_lang(self):
        raw = '```\n{"key": "value"}\n```'
        assert _parse_json_response(raw) == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_json_response("not json at all")


# ---------- Layer 1 ----------

class TestLayer1:
    @pytest.mark.asyncio
    async def test_call_layer1_valid(self):
        fixture = load_fixture("layer1_valid.json")
        mock_resp = make_mock_response(fixture)
        with patch("app.services.arbiter.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
            result = await call_layer1("test prompt")
        assert result["validation_status"] == "approved"
        assert result["quality_score"] == 0.82

    @pytest.mark.asyncio
    async def test_call_layer1_invalid(self):
        fixture = load_fixture("layer1_invalid.json")
        mock_resp = make_mock_response(fixture)
        with patch("app.services.arbiter.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
            result = await call_layer1("test prompt")
        assert result["validation_status"] == "rejected"
        assert "missing Data and Warrant" in result["feedback"]

    @pytest.mark.asyncio
    async def test_validate_turn_approved(self):
        fixture = load_fixture("layer1_valid.json")
        mock_resp = make_mock_response(fixture)
        with patch("app.services.arbiter.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
            result = await validate_turn(
                debate_topic="AI and labor markets",
                phase_0_structure={"hard_core": "AI affects jobs"},
                current_round=1,
                agent_name="TestAgent",
                school_of_thought="Empiricism",
                must_falsify=False,
                turn_content="AI is reshaping labor through task displacement.",
                toulmin_tags=[
                    {"type": "claim", "start": 0, "end": 20, "label": "test"},
                    {"type": "data", "start": 21, "end": 40, "label": "test"},
                    {"type": "warrant", "start": 41, "end": 50, "label": "test"},
                ],
                falsification_target=None,
            )
        assert result["validation_status"] == "approved"

    @pytest.mark.asyncio
    async def test_validate_phase0_declaration(self):
        fixture = load_fixture("layer1_valid.json")
        mock_resp = make_mock_response(fixture)
        with patch("app.services.arbiter.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
            result = await validate_phase0_declaration(
                debate_topic="AI and labor markets",
                declaration_content="My hard core is that AI creates net positive jobs.",
            )
        assert result["validation_status"] == "approved"


# ---------- Layer 2 ----------

class TestLayer2:
    @pytest.mark.asyncio
    async def test_call_layer2_evaluation(self):
        fixture = load_fixture("layer2_evaluation.json")
        mock_resp = make_mock_response(fixture)
        with patch("app.services.arbiter.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
            result = await call_layer2("test prompt")
        assert "evaluations" in result
        assert "synthesis" in result
        assert result["evaluations"][0]["composite_score"] == 0.766

    @pytest.mark.asyncio
    async def test_evaluate_debate(self):
        fixture = load_fixture("layer2_evaluation.json")
        mock_resp = make_mock_response(fixture)
        with patch("app.services.arbiter.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_resp)
            result = await evaluate_debate(
                debate_topic="AI and labor markets",
                category="economics",
                phase_0_structure={"hard_core": "AI affects jobs"},
                participants=[{"agent_id": "placeholder", "name": "TestAgent"}],
                full_transcript="Round 1: Agent argues X...",
                citation_challenges=[],
                audience_votes_summary={"total_votes": 0},
                relevant_graph_nodes=[],
            )
        assert len(result["evaluations"]) == 1
        assert len(result["synthesis"]["agreements"]) > 0


# ---------- API failure / retry ----------

class TestArbiterFailures:
    @pytest.mark.asyncio
    async def test_api_timeout_raises(self):
        """Verify that timeout from OpenRouter propagates as an exception."""
        from openai import APITimeoutError

        with patch("app.services.arbiter.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(
                side_effect=APITimeoutError(request=MagicMock())
            )
            with pytest.raises(APITimeoutError):
                await call_layer1("test prompt")

    @pytest.mark.asyncio
    async def test_malformed_json_response(self):
        """Arbiter returns non-JSON text — should raise JSONDecodeError."""
        msg = MagicMock()
        msg.content = "I don't understand the question."
        choice = MagicMock()
        choice.message = msg
        resp = MagicMock()
        resp.choices = [choice]

        with patch("app.services.arbiter.client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=resp)
            with pytest.raises(json.JSONDecodeError):
                await call_layer1("test prompt")
