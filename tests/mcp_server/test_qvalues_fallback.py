"""The off-manifold fallback: greedy Manhattan tie-break on flat states.

A tabular learner that has never visited a state reads ``initial_q_value``
for every action, so ``best_action``'s tie order returned ``move_set[0]`` --
a literal "always N" policy against any opponent whose trajectories the
2000-game self-play series never produced. The state key already carries the
opponent's RELATIVE cell, so a distance-greedy choice is available without
widening the state space or touching the learned manifold.
"""

from dataclasses import replace
import random

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


def test_cop_pursues_by_minimising_manhattan_distance(config, settings):
    """Opponent three rows south: S closes to 2, N opens to 4."""
    cop = QValues(config, settings, role="cop")

    assert cop.best_action(((3, 0), 0)) == "S"


def test_thief_evades_by_maximising_manhattan_distance(config, settings):
    """Opponent three rows north: S/E/W all open to 4, move-set order picks S."""
    thief = QValues(config, settings, role="thief")

    assert thief.best_action(((-3, 0), 0)) == "S"


def test_the_fallback_refuses_blocked_moves_and_may_choose_stay(config, settings):
    """S is barrier/edge blocked (bit 1), so the best legal closer is STAY."""
    cop = QValues(config, settings, role="cop")

    assert cop.best_action(((3, 0), 0b0010)) == "STAY"


def test_the_fallback_chooses_stay_when_every_direction_is_blocked(config, settings):
    cop = QValues(config, settings, role="cop")

    assert cop.best_action(((3, 0), 0b1111)) == "STAY"


def test_a_learned_state_is_never_overridden_by_the_fallback(config, settings):
    """One non-zero value means the state is on-manifold: greedy wins."""
    cop = QValues(config, settings, role="cop")
    cop.q_table[(((3, 0), 0), "N")] = 1.0

    assert cop.best_action(((3, 0), 0)) == "N"


def test_a_negative_learned_value_also_suppresses_the_fallback(config, settings):
    """Flatness is `all values == 0.0`, not `the maximum is 0.0`."""
    cop = QValues(config, settings, role="cop")
    cop.q_table[(((3, 0), 0), "S")] = -1.0

    assert cop.best_action(((3, 0), 0)) == "N"


def test_an_unobserved_opponent_keeps_the_move_set_tie_order(config, settings):
    """No relative cell means no distance to be greedy about."""
    cop = QValues(config, settings, role="cop")

    assert cop.best_action((None, 0)) == "N"


def test_a_table_built_without_a_role_keeps_its_original_behaviour(config, settings):
    """Role is opt-in; every existing construction site is unchanged."""
    roleless = QValues(config, settings)

    assert roleless.best_action(((3, 0), 0)) == "N"


def test_greedy_select_action_reaches_the_fallback(config, settings):
    """Match play is greedy (D5), so the fallback must survive select_action."""
    cop = QValues(config, replace(settings, exploration_rate=0.0), role="cop")

    assert all(
        cop.select_action(((3, 0), 0), random.Random(seed)) == "S"
        for seed in range(5)
    )
