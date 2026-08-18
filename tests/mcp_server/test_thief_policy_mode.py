"""The evader ships the same priority the pursuer does (audit S-1).

The cop was switched to `manhattan_primary` in Phase 8 and that was called the
single largest gain in the project. The thief kept `qtable_primary` — a
decision taken before the cop's swap was validated, and never revisited after
the Phase 9 retrain.

Distance-first is what an evader most needs, and the table was overriding it,
so the evader now TRAINS under `manhattan_primary` — which is also what makes
the self-play series contested rather than a rout.

The match-time story is less flattering and is recorded in
`test_match_policy_mode.py`: measured against a cop it never trained against,
distance-first survives 2.2% where table-first survives 8.0%, so the two
phases use different priorities. An earlier revision of this docstring quoted
93.0% survival for distance-first; that was measured against our own
pre-Phase-11 cop and did not generalise to any other opponent.
"""

from dataclasses import replace

import pytest

from engine.config import load_config
from strategy.qvalues import QValues
from strategy.settings import load_strategy_settings


@pytest.fixture
def config():
    return load_config("config/game.json")


def test_the_shipped_thief_is_configured_manhattan_primary():
    """Configuration, not a role check in Python — the same as the cop."""
    assert load_strategy_settings("thief").policy_mode == "manhattan_primary"


def test_distance_outranks_a_learned_value_for_the_evader(config):
    """A strong Q on a move that closes the gap must no longer win.

    Opponent three rows north. Under `qtable_primary` a learned value on N
    (toward the pursuer) decided the turn; under `manhattan_primary` only the
    distance-maximal moves are candidates at all.
    """
    settings = replace(load_strategy_settings("thief"), policy_mode="manhattan_primary")
    thief = QValues(config, settings, role="thief")
    state = ((-3, 0), 0)
    thief.q_table[(state, "N")] = 99.0

    assert thief.best_action(state) == "S"


def test_the_learned_table_still_breaks_ties_among_equally_evasive_moves(config):
    """Both strategies stay live: the table ranks what the distance rule allows."""
    settings = replace(load_strategy_settings("thief"), policy_mode="manhattan_primary")
    thief = QValues(config, settings, role="thief")
    # Opponent due north: S is uniquely best, so use a diagonal where E and S tie.
    state = ((-2, -2), 0)
    thief.q_table[(state, "E")] = 5.0

    assert thief.best_action(state) == "E"
