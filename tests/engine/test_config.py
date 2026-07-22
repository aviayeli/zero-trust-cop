"""Tests for engine.config module."""

import pytest
from engine.config import GameConfig, load_config


def test_load_config_from_game_json():
    """Test loading config from config/game.json and verifying all 7 fields."""
    config = load_config("config/game.json")

    assert isinstance(config, GameConfig)
    assert config.grid_size == 7
    assert config.cop_start == [0, 0]
    assert config.thief_start == [3, 3]
    assert config.move_set == ["N", "S", "E", "W", "STAY"]
    assert config.max_barriers == 14
    assert config.max_moves == 35
    assert config.survival_threshold == 35


def test_load_config_nonexistent_file():
    """Test that loading a non-existent config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent/path/config.json")


def test_load_config_missing_required_key(tmp_path):
    """Test that loading JSON missing a required key raises KeyError."""
    # Create a temporary JSON file with incomplete structure
    temp_config = tmp_path / "incomplete.json"
    temp_config.write_text('{"board_and_agents": {}}')

    with pytest.raises(KeyError):
        load_config(str(temp_config))
