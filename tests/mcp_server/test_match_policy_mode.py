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


def test_the_cop_trains_and_plays_on_the_same_priority_again():
    """The split still EXISTS; after diverse training it is not needed.

    Under self-play the two phases wanted different priorities, because a cop
    that trained under qtable_primary against a strong evader never won and
    learned nothing. Training against a POOL removed that: distance-first now
    measures best in both phases (100.0 / 29.8 / 28.0 against random / greedy
    / trained, where qtable_primary scores 99.5 / 20.0 / 24.5). The setting is
    retained because the phases are genuinely separable and the suite proves
    it; it simply does not need to differ today.
    """
    police = load_strategy_settings("police")

    assert police.policy_mode == "manhattan_primary"
    assert police.match_policy_mode == "manhattan_primary"


def test_the_evader_also_trains_and_plays_on_the_same_priority():
    """Diverse training reversed the evader's match-time preference too.

    Against a heuristic cop it never trained against, the evader now survives
    90.0% under distance-first against 83.8% table-first — and 69.8% carrying
    no table at all. Under self-play those figures were 2.2% and 8.0%, both
    far WORSE than the empty table.
    """
    thief = load_strategy_settings("thief")

    assert thief.policy_mode == "manhattan_primary"
    assert thief.match_policy_mode == "manhattan_primary"


def test_a_built_match_policy_uses_the_match_mode_not_the_training_one(
    config, monkeypatch
):
    """Prove the WIRING, not the value.

    Both keys currently hold the same mode, so comparing against a literal
    would pass even if `build_peer_policy` read the training key. The two are
    forced apart here so only the correct read can satisfy it.
    """
    real = load_strategy_settings("police")
    monkeypatch.setattr(
        "mcp_server.peer_policy.load_strategy_settings",
        lambda role, root=None: replace(
            real, policy_mode="qtable_primary",
            match_policy_mode="manhattan_primary",
        ),
    )

    policy = build_peer_policy("police", "cop", config)

    assert policy.qvalues.settings.policy_mode == "manhattan_primary"


def test_the_match_mode_is_still_required_configuration():
    """No invented default: a missing key must fail, like every other."""
    from strategy.settings import StrategySettings

    fields = StrategySettings.__dataclass_fields__

    assert "match_policy_mode" in fields
    assert fields["match_policy_mode"].default is __import__("dataclasses").MISSING
