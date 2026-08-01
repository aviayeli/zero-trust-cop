"""Fixtures for the offline trainer tests.

Every fixture redirects ``qtable_path`` under ``tmp_path``. A test run must
never write into the production ``data/`` directory, whose contents are the
committed Step 4 deliverables.
"""

from dataclasses import replace

import pytest

from engine.config import load_config
from strategy.settings import load_strategy_settings

SHARED_CONFIG_PATH = "config/game.json"


@pytest.fixture
def config():
    """The real shared GameConfig."""
    return load_config(SHARED_CONFIG_PATH)


@pytest.fixture
def training_settings(tmp_path):
    """Build both peers' settings, redirected to tmp_path with a short series."""

    def build(num_games):
        cop = replace(
            load_strategy_settings("police"),
            qtable_path=str(tmp_path / "q_table_police.json"),
            num_games=num_games,
        )
        thief = replace(
            load_strategy_settings("thief"),
            qtable_path=str(tmp_path / "q_table_thief.json"),
            num_games=num_games,
        )
        return cop, thief

    return build
