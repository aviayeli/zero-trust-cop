"""The learned tables now BEAT an empty one against an opponent never met.

This assertion is the inverse of the one it replaces, and the reversal is the
entire justification for the diverse-opponent phase. Under self-play the
shipped evader survived 2.2% against a heuristic pursuer where an EMPTY table
survived 69.8% — learning was a 30x liability, because values trained against
one adversary encode that adversary's habits and anything else exploits them.

Trained against a POOL (scripted, co-evolving, random, over varied barrier
layouts) the same measurement now reads 90.0% against 69.8%. The direction is
what is pinned here, not the magnitude: if an empty table ever beats the
trained one again, the phase has regressed and §10.10 must say so.
"""

from dataclasses import replace

import pytest

from engine.config import load_config
from scripts.offmanifold_probe import build_table, evaluate, start_pairs
from strategy.fallback import MANHATTAN_PRIMARY
from strategy.settings import load_strategy_settings

SEED = 20260817
PAIRS = 120


@pytest.fixture(scope="module")
def survival():
    """Evader survival against a heuristic cop, trained table vs empty."""
    config = replace(load_config("config/game.json"),
                     barrier_seed=BENCHMARK_BARRIER_SEED)
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

# The board these figures were measured on. `barrier_seed` left the shipped
# contract when we agreed a bare board with rstabcde -- their engine has no
# seeded-layout concept -- and a bare board makes the evader unbeatable:
# trained and empty tables both survive 100%, so the comparison says nothing.
# A strategy benchmark must pin its own board rather than move with a value
# we negotiate per opponent.
BENCHMARK_BARRIER_SEED = 20260818


def test_the_trained_evader_table_outperforms_an_empty_one(survival):
    """The result the diverse-opponent phase exists to produce."""
    assert survival["trained"] > survival["empty"], (
        "the learned evader table is a liability again — diverse training has "
        "regressed and §10.10 must be rewritten to say so"
    )


def test_the_gap_is_large_enough_to_be_a_finding_not_noise(survival):
    assert survival["trained"] - survival["empty"] > 10.0


def test_the_plan_publishes_this_result():
    """The reversal must be documented as a reversal, not quietly swapped."""
    plan = open("docs/PLAN.md", encoding="utf-8").read()

    assert "never trained against" in plan
    assert "2.2%" in plan, "§10.10 must keep stating what self-play measured"
