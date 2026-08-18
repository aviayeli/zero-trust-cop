"""Both learned tables are NET NEGATIVE against an opponent they never met.

This is the project's central empirical result and its least flattering one.
Self-play against a single adversary produces values that encode THAT
adversary's habits, and anything else exploits them. Measured against a
heuristic greedy pursuer — no learned values at all, and the likeliest
strategy an opposing group will field — the shipped evader survives a fraction
of what the SAME policy survives carrying an empty table.

It is pinned because it has already been got wrong once: a Phase 11 claim of
93.0% evader survival was measured against our own contemporaneous cop and did
not survive contact with any other opponent.
"""

from dataclasses import replace

import pytest

from engine.config import load_config
from strategy.fallback import MANHATTAN_PRIMARY
from strategy.settings import load_strategy_settings
from scripts.offmanifold_probe import build_table, evaluate, start_pairs

SEED = 20260817
PAIRS = 120


@pytest.fixture(scope="module")
def survival():
    """Evader survival against a heuristic cop, trained table vs empty."""
    config = load_config("config/game.json")
    police = load_strategy_settings("police")
    burglar = load_strategy_settings("thief")
    pairs = start_pairs(config, PAIRS, SEED)
    cop = build_table(config, replace(police, policy_mode=MANHATTAN_PRIMARY), "cop")

    def rate(table):
        evader = build_table(
            config, replace(burglar, policy_mode=burglar.match_policy_mode),
            "thief", table,
        )
        return 100.0 - evaluate(config, cop, evader, pairs, SEED)["capture_rate"]

    return {"trained": rate(burglar.qtable_path), "empty": rate(None)}


def test_an_empty_evader_table_outperforms_the_trained_one(survival):
    """The result the documentation must keep stating."""
    assert survival["empty"] > survival["trained"], (
        "the learned evader table stopped being a liability — §10.10 must be "
        "rewritten to say so"
    )


def test_the_gap_is_large_enough_to_be_a_finding_not_noise(survival):
    assert survival["empty"] - survival["trained"] > 20.0


def test_the_plan_publishes_this_result():
    """A finding this unflattering is exactly the one that quietly vanishes."""
    plan = open("docs/PLAN.md", encoding="utf-8").read()

    assert "never trained against" in plan
