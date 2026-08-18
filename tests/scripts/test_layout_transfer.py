"""The learned table's edge does NOT survive an unseen barrier layout.

Found by the multi-model debate (`scripts/multi_model_debate.py`), not by any
single-model sitting. The Anthropic panellist identified the mechanism from the
state key alone: `barrier_mask` is part of the key, so a layout the table never
trained on invalidates the learned states directly. It proposed the test; the
test confirmed it.

    layouts seen in training (0-19)    trained 60.6%  empty 50.7%   +9.9
    layouts never trained on           trained 55.1%  empty 57.4%   -2.2

So the +11.3pp the shipped layout shows is a favourable draw, not a
transferable gain. The DISTANCE RULE generalises; the learned increment on top
of it does not. Sample sizes come from config, and the assertion is on the
direction rather than the magnitude.
"""

import json
import statistics
from dataclasses import replace

import pytest

from engine.config import load_config
from scripts.offmanifold_probe import build_table, evaluate, start_pairs
from scripts.opponent_pool import load_training_settings
from strategy.fallback import MANHATTAN_PRIMARY
from strategy.settings import load_strategy_settings

SEED = 20260817
_VALIDATION = json.loads(open("config/benchmark.json", encoding="utf-8").read())[
    "layout_validation"
]
PAIRS = _VALIDATION["start_pairs"]
LAYOUTS = _VALIDATION["seeds"]
UNSEEN_BASE = 1000


def _rates(seeds):
    """(trained, empty) cop capture rates against a greedy evader per layout."""
    base = load_config("config/game.json")
    police = load_strategy_settings("police")
    burglar = load_strategy_settings("thief")
    trained, empty = [], []
    for seed in seeds:
        config = replace(base, barrier_seed=seed)
        pairs = start_pairs(config, PAIRS, SEED)
        evader = build_table(
            config, replace(burglar, policy_mode=MANHATTAN_PRIMARY), "thief"
        )
        cop = replace(police, policy_mode=MANHATTAN_PRIMARY)
        trained.append(
            evaluate(
                config, build_table(config, cop, "cop", police.qtable_path),
                evader, pairs, SEED,
            )["capture_rate"]
        )
        empty.append(
            evaluate(config, build_table(config, cop, "cop"), evader, pairs, SEED)[
                "capture_rate"
            ]
        )
    return statistics.mean(trained), statistics.mean(empty)


@pytest.fixture(scope="module")
def seen():
    return _rates(range(LAYOUTS))


@pytest.fixture(scope="module")
def unseen():
    trained_pool = load_training_settings().layout_seeds
    start = max(UNSEEN_BASE, trained_pool + 1)
    return _rates(range(start, start + LAYOUTS))


def test_the_probe_seeds_are_genuinely_outside_the_training_pool():
    """The first version of this test was CONFOUNDED — seeds 0-19 are trained on."""
    assert UNSEEN_BASE > load_training_settings().layout_seeds


def test_the_learned_table_wins_on_layouts_it_trained_on(seen):
    trained, empty = seen

    assert trained > empty, "the learned table lost even on its own layouts"


def test_the_edge_does_not_transfer_to_an_unseen_layout(unseen):
    """The finding. If this ever passes comfortably, the table has generalised.

    Asserted as "no meaningful edge" rather than "strictly worse": the measured
    gap is -2.2 points, which is a failure to transfer, not a reliable loss.
    """
    trained, empty = unseen

    assert trained < empty + 5.0, (
        "the learned table now transfers to unseen layouts — §10.10's "
        "generalisation limit must be rewritten"
    )


def test_the_plan_publishes_the_transfer_gap(seen, unseen):
    """A limit this unflattering is the one that quietly disappears."""
    plan = open("docs/PLAN.md", encoding="utf-8").read().lower()

    assert "does not transfer" in plan
    assert "barrier_mask" in plan
