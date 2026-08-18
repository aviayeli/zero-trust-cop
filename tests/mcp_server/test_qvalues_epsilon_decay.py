"""Tests for epsilon decay on QValues."""

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


def test_epsilon_starts_at_exploration_rate(config, settings):
    """Mutable epsilon is seeded from the frozen config value."""
    values = QValues(config, settings)
    assert values.epsilon == settings.exploration_rate


def test_decay_epsilon_multiplies_by_decay_factor(config, settings):
    """decay_epsilon() multiplies the mutable epsilon by decay_factor."""
    values = QValues(config, settings)
    initial_epsilon = values.epsilon
    values.decay_epsilon()
    assert values.epsilon == pytest.approx(
        initial_epsilon * settings.epsilon_decay_factor
    )


def test_epsilon_never_falls_below_floor(config, settings):
    """Repeated decay_epsilon() calls clamp at epsilon_floor.

    The iteration count is DERIVED from the configured schedule rather than
    fixed: a hardcoded 2,500 silently stopped reaching the floor when
    `epsilon_decay_factor` was retuned from 0.999 to 0.999744 for the
    10,000-episode diverse run.
    """
    import math

    values = QValues(config, settings)
    needed = math.ceil(
        math.log(settings.epsilon_floor / settings.exploration_rate)
        / math.log(settings.epsilon_decay_factor)
    )
    for _ in range(needed + 1):
        values.decay_epsilon()

    assert values.epsilon == settings.epsilon_floor


def _greedy_table(values, state):
    """Populate one state so that W is the unique best action."""
    for action, value in (("N", 1.0), ("S", 2.0), ("E", 1.0), ("W", 10.0), ("STAY", 1.0)):
        values.q_table[(state, action)] = value


def test_select_action_honours_decayed_epsilon_not_frozen_config(config, settings):
    """One real decay drives epsilon to the 0.0 floor and makes selection greedy."""
    decayed_settings = replace(
        settings, exploration_rate=0.5, epsilon_decay_factor=0.0, epsilon_floor=0.0
    )
    values = QValues(config, decayed_settings)
    state = values.state_key((3, 3), None, set())
    _greedy_table(values, state)

    # decay_epsilon() itself must drive the change; nothing pokes _epsilon directly.
    values.decay_epsilon()
    assert values.epsilon == 0.0
    assert decayed_settings.exploration_rate == 0.5

    for seed in range(10):
        assert values.select_action(state, random.Random(seed)) == "W"


def test_select_action_explores_before_decay(config, settings):
    """Guard the test above: at the UNDECAYED rate selection is not always greedy."""
    exploring_settings = replace(
        settings, exploration_rate=1.0, epsilon_decay_factor=0.0, epsilon_floor=0.0
    )
    values = QValues(config, exploring_settings)
    state = values.state_key((3, 3), None, set())
    _greedy_table(values, state)

    chosen = {values.select_action(state, random.Random(seed)) for seed in range(10)}
    assert chosen != {"W"}
