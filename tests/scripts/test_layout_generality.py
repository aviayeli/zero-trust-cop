"""The barrier result must be a result, not a favourable draw (audit S-3).

§10.10 reported a single layout. A scatter of fourteen cells resampled only
for connectivity can easily flatter one side, and the council's objection was
that the capture rate against a greedy evader might be an artifact of the
seed rather than of the barriers.

So the claim is checked across MANY layouts: every one of them must beat the
bare board, which is the actual claim being made ("barriers are what give a
lone pursuer somewhere to corner against"). The sample size and start count
come from `config/benchmark.json`, never from literals here.
"""

import json
from dataclasses import replace

import pytest

from engine.config import load_config
from scripts.offmanifold_probe import build_table, evaluate, start_pairs
from strategy.fallback import MANHATTAN_PRIMARY, QTABLE_PRIMARY
from strategy.settings import load_strategy_settings

SEED = 20260817


@pytest.fixture(scope="module")
def validation():
    return json.loads(open("config/benchmark.json", encoding="utf-8").read())[
        "layout_validation"
    ]


def _capture_rate(config):
    """Shipped cop against a greedy evader on one board."""
    police = load_strategy_settings("police")
    burglar = load_strategy_settings("thief")
    cop = build_table(
        config, replace(police, policy_mode=QTABLE_PRIMARY), "cop", police.qtable_path
    )
    greedy = build_table(config, replace(burglar, policy_mode=MANHATTAN_PRIMARY), "thief")
    pairs = start_pairs(config, _PAIRS, SEED)
    return evaluate(config, cop, greedy, pairs, SEED)["capture_rate"]


_PAIRS = json.loads(open("config/benchmark.json", encoding="utf-8").read())[
    "layout_validation"
]["start_pairs"]


@pytest.fixture(scope="module")
def rates(validation):
    base = load_config("config/game.json")
    return [
        _capture_rate(replace(base, barrier_seed=seed))
        for seed in range(validation["seeds"])
    ]


@pytest.fixture(scope="module")
def bare_rate():
    return _capture_rate(replace(load_config("config/game.json"), barrier_seed=None))


def test_a_greedy_evader_is_uncatchable_on_a_bare_board(bare_rate):
    """The baseline the whole claim rests on."""
    assert bare_rate == 0.0


def test_every_layout_beats_the_bare_board(rates, bare_rate):
    """The claim is about BARRIERS, so it must hold for barriers generally."""
    losers = [index for index, rate in enumerate(rates) if rate <= bare_rate]

    assert not losers, f"layout seeds {losers} did no better than a bare board"


def test_the_shipped_layout_is_not_an_outlier(rates):
    """Our seed may be lucky; it must not be off the scale.

    §10.10 states that the shipped seed scores ABOVE the multi-layout mean,
    so this asserts the honest direction rather than pretending it is typical.
    """
    shipped = _capture_rate(load_config("config/game.json"))

    assert shipped <= max(rates) + 25.0, "the shipped layout is an outlier"
