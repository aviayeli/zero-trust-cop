"""Series length comes from the private [strategy] block, not the shared config.

Also pins the production signature: pytest constructs such as ``tmp_path``
must not appear in it, and ``num_games`` must not be caller-supplied, or the
D3 requirement would be satisfied by whoever happens to call the trainer.
"""

import inspect
import json
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.run_tournament import train_tournament
from strategy.settings import load_strategy_settings


def test_production_signature_is_free_of_test_constructs():
    parameters = inspect.signature(train_tournament).parameters

    assert "tmp_path" not in parameters


def test_num_games_is_not_a_caller_supplied_argument():
    parameters = inspect.signature(train_tournament).parameters

    assert "num_games" not in parameters


def test_series_length_comes_from_the_private_strategy_block(
    config, training_settings
):
    cop_settings, thief_settings = training_settings(num_games=4)

    scores = train_tournament(config, cop_settings, thief_settings, seed=11)

    assert len(scores) == 4


def test_a_different_private_series_length_is_honoured(config, training_settings):
    cop_settings, thief_settings = training_settings(num_games=7)

    scores = train_tournament(config, cop_settings, thief_settings, seed=11)

    assert len(scores) == 7


def test_the_shared_config_declares_the_league_series_length():
    """D3: game.json is the Step-0 contract, and it declares the LEAGUE
    series length (6 games) — not the private training length, which each
    peer sets to 2000 in its own game.toml. The two must never be conflated."""
    shared = json.loads(Path("config/game.json").read_text())

    assert shared["network_and_league"]["num_games"] == 6


def test_both_peers_privately_declare_the_training_series_length():
    assert load_strategy_settings("police").num_games == 2000
    assert load_strategy_settings("thief").num_games == 2000


def test_disagreeing_series_lengths_fail_loudly(config, training_settings):
    cop_settings, thief_settings = training_settings(num_games=3)
    thief_settings = replace(thief_settings, num_games=2)

    with pytest.raises(ValueError):
        train_tournament(config, cop_settings, thief_settings, seed=1)


def test_the_trained_table_carries_its_engine_role():
    """The trainer must hand QValues the role its fallback needs."""
    from engine.config import load_config
    from scripts.run_tournament import build_policy
    from strategy.settings import load_strategy_settings

    config = load_config("config/game.json")
    cop = build_policy("cop", config, load_strategy_settings("police"))
    thief = build_policy("thief", config, load_strategy_settings("thief"))

    assert (cop.qvalues.role, thief.qvalues.role) == ("cop", "thief")
