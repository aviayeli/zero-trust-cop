"""Tests for private per-peer strategy settings."""

import os
import tomllib

import pytest

from strategy.settings import load_strategy_settings, strategy_settings_path


def test_strategy_settings_paths_are_role_separated():
    """Each peer resolves its own private strategy file."""
    police_path = strategy_settings_path("police")
    thief_path = strategy_settings_path("thief")
    assert police_path == os.path.join("config", "police", "game.toml")
    assert thief_path == os.path.join("config", "thief", "game.toml")
    assert police_path != thief_path


def test_strategy_settings_path_honours_config_root_override():
    assert strategy_settings_path("police", config_root="/tmp/x") == os.path.join(
        "/tmp/x", "police", "game.toml"
    )


def test_strategy_settings_path_honours_environment(monkeypatch):
    monkeypatch.setenv("ZTC_CONFIG_ROOT", "/tmp/strategy-config")
    assert strategy_settings_path("thief") == os.path.join(
        "/tmp/strategy-config", "thief", "game.toml"
    )


def test_loads_real_police_settings():
    settings = load_strategy_settings("police")
    assert settings.learning_rate == 0.1
    assert settings.discount_factor == 0.9
    assert settings.exploration_rate == 0.1
    assert settings.initial_q_value == 0.0
    assert settings.invalid_move_penalty == -1.0
    assert settings.qtable_path


def test_loaded_setting_types():
    settings = load_strategy_settings("police")
    assert all(
        isinstance(value, float)
        for value in (
            settings.learning_rate,
            settings.discount_factor,
            settings.exploration_rate,
            settings.initial_q_value,
            settings.invalid_move_penalty,
        )
    )
    assert isinstance(settings.qtable_path, str)


def test_peers_have_separate_qtable_paths():
    assert (
        load_strategy_settings("police").qtable_path
        != load_strategy_settings("thief").qtable_path
    )


def test_missing_game_toml_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_strategy_settings("police", config_root=str(tmp_path))


def test_missing_strategy_block_raises_key_error(tmp_path):
    role_dir = tmp_path / "police"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text("[other]\nvalue = 1\n")
    with pytest.raises(KeyError):
        load_strategy_settings("police", config_root=str(tmp_path))


@pytest.mark.parametrize("missing_key", ["learning_rate", "qtable_path"])
def test_missing_strategy_field_raises_key_error(tmp_path, missing_key):
    fields = {
        "learning_rate": "0.1",
        "discount_factor": "0.9",
        "exploration_rate": "0.1",
        "initial_q_value": "0.0",
        "invalid_move_penalty": "-1.0",
        "honesty_prior": "0.5",
        "qtable_path": '"qtable.json"',
    }
    del fields[missing_key]
    role_dir = tmp_path / "police"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text(
        "[strategy]\n" + "\n".join(f"{key} = {value}" for key, value in fields.items())
    )
    with pytest.raises(KeyError):
        load_strategy_settings("police", config_root=str(tmp_path))


def test_malformed_toml_raises(tmp_path):
    role_dir = tmp_path / "police"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text("[strategy\n")
    with pytest.raises(tomllib.TOMLDecodeError):
        load_strategy_settings("police", config_root=str(tmp_path))


def test_values_come_from_file(tmp_path):
    role_dir = tmp_path / "police"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text(
        """[strategy]
learning_rate = 0.42
discount_factor = 0.9
exploration_rate = 0.1
initial_q_value = 0.0
invalid_move_penalty = -1.0
step_cost = -0.01
honesty_prior = 0.5
qtable_path = "custom-qtable.json"
epsilon_decay_factor = 0.999
epsilon_floor = 0.01
num_games = 2000
hint_max_words = 15
match_exploration_rate = 0.0
policy_mode = "qtable_primary"
"""
    )
    assert load_strategy_settings("police", config_root=str(tmp_path)).learning_rate == 0.42
