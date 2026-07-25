"""Tests for tabular Q-learning updates and persistence."""

import json
from dataclasses import replace

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


def test_update_moves_value_by_exact_td_error(config, settings):
    tuned = replace(settings, learning_rate=0.5, discount_factor=0.9)
    values = QValues(config, tuned)
    state = values.state_key((3, 3), None, set())
    next_state = values.state_key((3, 4), (4, 4), set())

    values.q_table[(state, "N")] = 0.0
    values.update(state, "N", 10, next_state, terminal=False)

    assert values.q_value(state, "N") == 5.0

    values.q_table[(state, "S")] = 2.0
    values.q_table[(next_state, "E")] = 4.0
    values.update(state, "S", 1, next_state, terminal=False)

    assert values.q_value(state, "S") == 3.3


def test_terminal_update_drops_bootstrap_term(config, settings):
    tuned = replace(settings, learning_rate=0.5, discount_factor=0.9)
    values = QValues(config, tuned)
    state = values.state_key((3, 3), None, set())
    next_state = values.state_key((3, 4), (4, 4), set())
    values.q_table[(state, "N")] = 2.0
    values.q_table[(next_state, "E")] = 100.0

    values.update(state, "N", 10, next_state, terminal=True)

    assert values.q_value(state, "N") == 6.0


def test_qtable_round_trip(config, settings, tmp_path):
    path = tmp_path / "qtable.json"
    values = QValues(config, settings)
    state = values.state_key((3, 3), (4, 4), {(3, 2)})
    values.q_table[(state, "N")] = 1.25
    values.q_table[(state, "S")] = -2.5

    values.save(path)
    loaded = QValues(config, settings)
    loaded.load(path)

    assert loaded.q_table == values.q_table


def test_load_rejects_a_different_state_layout(config, settings, tmp_path):
    path = tmp_path / "wrong-layout.json"
    path.write_text(json.dumps({"state_layout_version": -1, "q_values": []}))

    with pytest.raises(ValueError):
        QValues(config, settings).load(path)


def test_save_creates_a_missing_parent_directory(config, settings, tmp_path):
    path = tmp_path / "new" / "nested" / "qtable.json"

    QValues(config, settings).save(path)

    assert path.is_file()
