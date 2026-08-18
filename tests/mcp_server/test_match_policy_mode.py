"""Training priority and match priority are separate settings (audit S-1).

`policy_mode` governed both, and the two want different things. A cop that
trains under `qtable_primary` against a competent evader never wins — self-play
collapsed to a 0.05% capture rate, so every learned value was recorded in a
series the cop lost, and the table was worthless. Training under
`manhattan_primary` keeps the series contested (52.3%) and produces a table
worth having; that same table then measures BEST at match time under
`qtable_primary` (47.5% against a greedy evader, against 21.0%).

This is the split `exploration_rate` / `match_exploration_rate` already makes
for the same reason: what makes a good learner is not what makes a good
competitor.
"""

from dataclasses import replace

import pytest

from engine.config import load_config
from mcp_server.peer_policy import build_peer_policy
from strategy.settings import load_strategy_settings


@pytest.fixture
def config():
    return load_config("config/game.json")


def test_both_peers_declare_a_match_policy_mode():
    for role in ("police", "thief"):
        assert load_strategy_settings(role).match_policy_mode


def test_the_cop_trains_on_one_priority_and_plays_on_another():
    """The whole point: a contested trainer, a competitive player."""
    police = load_strategy_settings("police")

    assert police.policy_mode == "manhattan_primary"
    assert police.match_policy_mode == "qtable_primary"


def test_the_evader_also_trains_and_plays_on_different_priorities():
    """Distance-first made the SERIES contested; it plays worse in a match.

    Measured against a heuristic cop — the likeliest opposing strategy, and
    one the evader never trained against — distance-first survives 2.2% where
    table-first survives 8.0%. Both are poor. The split is what lets the
    better training regime and the better match regime coexist.
    """
    thief = load_strategy_settings("thief")

    assert thief.policy_mode == "manhattan_primary"
    assert thief.match_policy_mode == "qtable_primary"


def test_a_built_match_policy_uses_the_match_mode_not_the_training_one(config):
    """Loudly, at the composition root — a silent fallback would lose points."""
    policy = build_peer_policy("police", "cop", config)

    assert policy.qvalues.settings.policy_mode == "qtable_primary"


def test_the_match_mode_is_still_required_configuration():
    """No invented default: a missing key must fail, like every other."""
    from strategy.settings import StrategySettings

    fields = StrategySettings.__dataclass_fields__

    assert "match_policy_mode" in fields
    assert fields["match_policy_mode"].default is __import__("dataclasses").MISSING
