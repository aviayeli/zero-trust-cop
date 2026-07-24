"""Shared test fixtures for engine test modules."""

import pytest

from engine.config import load_config
from engine.game_loop import GameEpisode
from engine.board import Board


def _make_episode():
    """Build a fresh GameEpisode from the game config."""
    config = load_config("config/game.json")
    return GameEpisode(config)


def _make_board():
    """Build a fresh 7x7 board from the game config."""
    config = load_config("config/game.json")
    return Board(config)


@pytest.fixture
def make_episode():
    return _make_episode


@pytest.fixture
def make_board():
    return _make_board
