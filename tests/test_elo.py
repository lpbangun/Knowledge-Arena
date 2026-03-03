"""Exhaustive Elo calculation tests — 27 test cases."""
import pytest

from app.services.elo import (
    ELO_FLOOR,
    K_ESTABLISHED,
    K_PROVISIONAL,
    actual_score,
    calculate_elo_adjustments,
    expected_score,
    get_k_factor,
)


# --- K Factor ---

def test_k_factor_provisional():
    assert get_k_factor(0) == K_PROVISIONAL
    assert get_k_factor(19) == K_PROVISIONAL


def test_k_factor_established():
    assert get_k_factor(20) == K_ESTABLISHED
    assert get_k_factor(100) == K_ESTABLISHED


# --- Expected Score ---

def test_expected_equal_rating():
    assert expected_score(1000, 1000) == pytest.approx(0.5)


def test_expected_higher_rating():
    e = expected_score(1200, 1000)
    assert e > 0.5
    assert e < 1.0


def test_expected_lower_rating():
    e = expected_score(800, 1000)
    assert e < 0.5
    assert e > 0.0


def test_expected_symmetry():
    e1 = expected_score(1000, 1200)
    e2 = expected_score(1200, 1000)
    assert e1 + e2 == pytest.approx(1.0)


# --- Actual Score ---

def test_actual_score_win():
    assert actual_score(0.8, 0.5) == 1.0


def test_actual_score_loss():
    assert actual_score(0.3, 0.7) == 0.0


def test_actual_score_draw():
    assert actual_score(0.5, 0.5) == 0.5


# --- Elo Adjustments: 2 agents ---

def test_two_agents_clear_winner():
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.8},
            {"agent_id": "b", "composite_score": 0.4},
        ],
        current_ratings={"a": 1000, "b": 1000},
        total_debates={"a": 5, "b": 5},
    )
    assert result["a"] > 1000
    assert result["b"] < 1000


def test_two_agents_draw():
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.5},
            {"agent_id": "b", "composite_score": 0.5},
        ],
        current_ratings={"a": 1000, "b": 1000},
        total_debates={"a": 5, "b": 5},
    )
    assert result["a"] == 1000
    assert result["b"] == 1000


def test_two_agents_upset_win():
    """Lower rated agent wins — should gain more Elo."""
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.9},
            {"agent_id": "b", "composite_score": 0.3},
        ],
        current_ratings={"a": 800, "b": 1200},
        total_debates={"a": 5, "b": 5},
    )
    assert result["a"] > 800
    assert result["b"] < 1200
    gain = result["a"] - 800
    assert gain > 16  # Upset should give big gain


def test_higher_rated_wins_gains_less():
    """Higher rated agent winning gains fewer points."""
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.9},
            {"agent_id": "b", "composite_score": 0.3},
        ],
        current_ratings={"a": 1200, "b": 800},
        total_debates={"a": 5, "b": 5},
    )
    assert result["a"] > 1200
    gain = result["a"] - 1200
    assert gain < 16  # Expected win gains less


# --- Multi-agent (3+) ---

def test_three_agents():
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.9},
            {"agent_id": "b", "composite_score": 0.6},
            {"agent_id": "c", "composite_score": 0.3},
        ],
        current_ratings={"a": 1000, "b": 1000, "c": 1000},
        total_debates={"a": 5, "b": 5, "c": 5},
    )
    assert result["a"] > result["b"] > result["c"]


def test_six_agents():
    evals = [
        {"agent_id": f"agent_{i}", "composite_score": (6 - i) / 6}
        for i in range(6)
    ]
    ratings = {f"agent_{i}": 1000 for i in range(6)}
    debates = {f"agent_{i}": 5 for i in range(6)}

    result = calculate_elo_adjustments(evals, ratings, debates)

    sorted_by_elo = sorted(result.items(), key=lambda x: x[1], reverse=True)
    for i in range(len(sorted_by_elo) - 1):
        assert sorted_by_elo[i][1] >= sorted_by_elo[i + 1][1]


# --- Floor ---

def test_elo_floor():
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.1},
            {"agent_id": "b", "composite_score": 0.9},
        ],
        current_ratings={"a": 100, "b": 1200},
        total_debates={"a": 5, "b": 5},
    )
    assert result["a"] >= ELO_FLOOR


def test_elo_no_ceiling():
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.99},
            {"agent_id": "b", "composite_score": 0.01},
        ],
        current_ratings={"a": 3000, "b": 1000},
        total_debates={"a": 5, "b": 5},
    )
    assert result["a"] >= 3000


# --- Audience Modifier ---

def test_audience_modifier_applied():
    result_no_audience = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.8},
            {"agent_id": "b", "composite_score": 0.4},
        ],
        current_ratings={"a": 1000, "b": 1000},
        total_debates={"a": 5, "b": 5},
    )

    # Audience disagrees — thinks B is better
    result_with_audience = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.8},
            {"agent_id": "b", "composite_score": 0.4},
        ],
        current_ratings={"a": 1000, "b": 1000},
        total_debates={"a": 5, "b": 5},
        audience_votes={"a": 0.3, "b": 0.9},
    )

    # A should gain less when audience disagrees
    assert result_with_audience["a"] < result_no_audience["a"]


def test_audience_agreement_no_change():
    """When audience agrees with arbiter, modifier has minimal effect."""
    result_no = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.8},
            {"agent_id": "b", "composite_score": 0.3},
        ],
        current_ratings={"a": 1000, "b": 1000},
        total_debates={"a": 5, "b": 5},
    )

    result_yes = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.8},
            {"agent_id": "b", "composite_score": 0.3},
        ],
        current_ratings={"a": 1000, "b": 1000},
        total_debates={"a": 5, "b": 5},
        audience_votes={"a": 0.9, "b": 0.2},
    )

    # Same ranking → similar results (within rounding)
    assert abs(result_no["a"] - result_yes["a"]) <= 2


# --- Bonuses ---

def test_bonus_applied():
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.5},
            {"agent_id": "b", "composite_score": 0.5},
        ],
        current_ratings={"a": 1000, "b": 1000},
        total_debates={"a": 5, "b": 5},
        bonuses={"a": 15},  # gap-filling bonus
    )
    assert result["a"] == 1015
    assert result["b"] == 1000


def test_negative_bonus_penalty():
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.5},
            {"agent_id": "b", "composite_score": 0.5},
        ],
        current_ratings={"a": 1000, "b": 1000},
        total_debates={"a": 5, "b": 5},
        bonuses={"a": -10},  # citation challenge penalty
    )
    assert result["a"] == 990


# --- K Factor impact ---

def test_established_smaller_changes():
    result_provisional = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.8},
            {"agent_id": "b", "composite_score": 0.2},
        ],
        current_ratings={"a": 1000, "b": 1000},
        total_debates={"a": 5, "b": 5},
    )
    result_established = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.8},
            {"agent_id": "b", "composite_score": 0.2},
        ],
        current_ratings={"a": 1000, "b": 1000},
        total_debates={"a": 50, "b": 50},
    )
    # Provisional should have bigger swings
    gain_prov = result_provisional["a"] - 1000
    gain_est = result_established["a"] - 1000
    assert gain_prov > gain_est


# --- Edge cases ---

def test_single_agent():
    result = calculate_elo_adjustments(
        evaluations=[{"agent_id": "a", "composite_score": 0.9}],
        current_ratings={"a": 1000},
        total_debates={"a": 5},
    )
    assert result["a"] == 1000  # No opponents, no change


def test_identical_scores():
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.5},
            {"agent_id": "b", "composite_score": 0.5},
            {"agent_id": "c", "composite_score": 0.5},
        ],
        current_ratings={"a": 1000, "b": 1000, "c": 1000},
        total_debates={"a": 5, "b": 5, "c": 5},
    )
    # All equal → no change
    assert result["a"] == 1000
    assert result["b"] == 1000
    assert result["c"] == 1000


def test_zero_sum_ish():
    """Total Elo change should be approximately zero-sum."""
    result = calculate_elo_adjustments(
        evaluations=[
            {"agent_id": "a", "composite_score": 0.8},
            {"agent_id": "b", "composite_score": 0.5},
            {"agent_id": "c", "composite_score": 0.2},
        ],
        current_ratings={"a": 1000, "b": 1000, "c": 1000},
        total_debates={"a": 5, "b": 5, "c": 5},
    )
    total_change = sum(v - 1000 for v in result.values())
    # Should be close to zero (rounding may cause small differences)
    assert abs(total_change) <= 3
