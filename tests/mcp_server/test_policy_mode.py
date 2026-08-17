"""Manhattan-primary policy: distance decides, the learned table breaks ties.

The shipped cop used to read its Q-table first and consult the distance rule
only where the table was flat, which measured 69.2% against the trained thief
while a pure heuristic measured 98.2% (PLAN.md §10.10). Inverting the priority
keeps BOTH strategies live on every decision: the heuristic narrows the legal
moves to those that are distance-optimal, and the table chooses among them.

The mode is per-peer configuration (`policy_mode` in each private
`game.toml`), not a role check in Python, so the cop and thief can differ
without either being special-cased in code.
"""

from dataclasses import replace

import pytest

from engine.config import load_config
from strategy.qvalues import QValues
from strategy.settings import load_strategy_settings


@pytest.fixture
def config():
    return load_config("config/game.json")


@pytest.fixture
def manhattan(config):
    """A cop whose configured mode is manhattan_primary."""
    settings = replace(load_strategy_settings("police"), policy_mode="manhattan_primary")
    return QValues(config, settings, role="cop")


@pytest.fixture
def qtable_first(config):
    """A cop still on the old priority, for contrast."""
    settings = replace(load_strategy_settings("police"), policy_mode="qtable_primary")
    return QValues(config, settings, role="cop")


def test_the_shipped_cop_is_configured_manhattan_primary():
    """The swap must be real configuration, not a test-only construction."""
    assert load_strategy_settings("police").policy_mode == "manhattan_primary"


def test_distance_now_outranks_a_learned_value(manhattan):
    """The inversion itself: a strong Q on a worse move no longer wins.

    Opponent three rows south. N is distance 4 and carries the only learned
    value; S is distance 2. Under the old priority this returned N.
    """
    manhattan.q_table[(((3, 0), 0), "N")] = 99.0

    assert manhattan.best_action(((3, 0), 0)) == "S"


def test_the_old_priority_still_prefers_the_learned_value(qtable_first):
    """Contrast case, so the two modes are proven genuinely different."""
    qtable_first.q_table[(((3, 0), 0), "N")] = 99.0

    assert qtable_first.best_action(((3, 0), 0)) == "N"


def test_the_table_breaks_ties_between_equally_good_moves(manhattan):
    """Opponent on the diagonal: S and E both close the gap by one."""
    manhattan.q_table[(((3, 3), 0), "E")] = 5.0

    assert manhattan.best_action(((3, 3), 0)) == "E"


def test_a_tie_break_never_escapes_the_distance_optimal_set(manhattan):
    """A huge value on a distance-losing move must still be ignored."""
    manhattan.q_table[(((3, 3), 0), "N")] = 1000.0
    manhattan.q_table[(((3, 3), 0), "S")] = 1.0

    assert manhattan.best_action(((3, 3), 0)) == "S"


def test_untied_moves_ignore_the_table_entirely(manhattan):
    """One uniquely-optimal move leaves the table nothing to decide."""
    assert manhattan.best_action(((3, 0), 0)) == "S"


def test_ties_with_no_learned_values_keep_move_set_order(manhattan):
    """S precedes E in move_set, so a flat tie is still deterministic."""
    assert manhattan.best_action(((3, 3), 0)) == "S"


def test_blocked_moves_are_excluded_before_the_tie_break(manhattan):
    """S is blocked (bit 1); E is the only remaining distance-optimal move."""
    manhattan.q_table[(((3, 3), 0b0010), "S")] = 1000.0

    assert manhattan.best_action(((3, 3), 0b0010)) == "E"


def test_an_unobserved_opponent_falls_back_to_the_table(manhattan):
    """No relative cell means no distance, so the table decides alone."""
    manhattan.q_table[(((None), 0), "W")] = 3.0

    assert manhattan.best_action((None, 0)) == "W"


def test_a_thief_configured_manhattan_primary_maximises_distance(config):
    settings = replace(load_strategy_settings("thief"), policy_mode="manhattan_primary")
    thief = QValues(config, settings, role="thief")

    assert thief.best_action(((-3, 0), 0)) == "S"


def test_an_unknown_policy_mode_fails_loudly(config):
    settings = replace(load_strategy_settings("police"), policy_mode="wishful")
    values = QValues(config, settings, role="cop")

    with pytest.raises(ValueError, match="policy_mode"):
        values.best_action(((3, 0), 0))
