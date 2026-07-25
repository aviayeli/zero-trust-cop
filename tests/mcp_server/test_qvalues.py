"""Tests for tabular Q-learning values."""

import random
from dataclasses import replace

import pytest

from engine.config import load_config
from strategy.qvalues import QValues
from strategy.settings import load_strategy_settings


@pytest.fixture
def config():
    return load_config("config/game.json")


@pytest.fixture
def settings():
    return load_strategy_settings("police")


def test_state_key_contains_relative_opponent_and_barrier_mask(config, settings):
    values = QValues(config, settings)

    state = values.state_key((3, 3), (5, 2), {(2, 3)})

    assert state == ((2, -1), 1)


def test_state_key_uses_none_for_an_unobserved_opponent(config, settings):
    values = QValues(config, settings)

    assert values.state_key((3, 3), None, set()) == (None, 0)


@pytest.mark.parametrize(
    ("barrier", "expected_mask"),
    [((2, 3), 1), ((4, 3), 2), ((3, 2), 4), ((3, 4), 8)],
)
def test_state_key_uses_documented_barrier_bit_order(
    config, settings, barrier, expected_mask
):
    values = QValues(config, settings)

    assert values.state_key((3, 3), None, {barrier}) == (None, expected_mask)


def test_state_key_treats_off_board_neighbours_as_blocked(config, settings):
    values = QValues(config, settings)

    assert values.state_key((0, 0), None, set()) == (None, 5)


def test_state_key_excludes_move_count(config, settings):
    values = QValues(config, settings)

    first_turn_state = values.state_key((3, 3), (4, 4), set())
    later_turn_state = values.state_key((3, 3), (4, 4), set())

    assert first_turn_state == later_turn_state
    assert len(first_turn_state) == 2


def test_unseen_value_uses_configured_initial_value(config, settings):
    values = QValues(config, settings)
    state = values.state_key((3, 3), None, set())

    assert values.q_value(state, "N") == settings.initial_q_value


@pytest.mark.parametrize(
    ("role", "outcome", "expected"),
    [
        ("cop", "capture", 20),
        ("thief", "capture", 5),
        ("cop", "survival", 5),
        ("thief", "survival", 10),
        ("cop", "tie", 2),
        ("thief", "tie", 2),
        ("cop", "technical_loss", 0),
        ("thief", "technical_loss", 0),
    ],
)
def test_rewards_come_from_game_config(config, settings, role, outcome, expected):
    assert QValues(config, settings).reward(role, outcome) == expected


def test_reward_rejects_unknown_role_or_outcome(config, settings):
    values = QValues(config, settings)

    with pytest.raises(ValueError):
        values.reward("unknown", "capture")
    with pytest.raises(ValueError):
        values.reward("cop", "unknown")


def test_best_action_is_greedy_with_deterministic_tie_breaking(config, settings):
    values = QValues(config, settings)
    state = values.state_key((3, 3), None, set())
    values.q_table[(state, "S")] = 7.0
    values.q_table[(state, "E")] = 7.0

    assert values.best_action(state) == "S"


def test_select_action_is_reproducible_and_zero_epsilon_is_greedy(config, settings):
    state = QValues(config, settings).state_key((3, 3), None, set())
    exploratory = replace(settings, exploration_rate=1.0)
    first = QValues(config, exploratory)
    second = QValues(config, exploratory)
    first_rng = random.Random(9)
    second_rng = random.Random(9)

    assert [first.select_action(state, first_rng) for _ in range(5)] == [
        second.select_action(state, second_rng) for _ in range(5)
    ]

    zero_epsilon = QValues(config, replace(settings, exploration_rate=0.0))
    zero_epsilon.q_table[(state, "W")] = 3.0
    assert all(
        zero_epsilon.select_action(state, random.Random(seed)) == "W"
        for seed in range(5)
    )

