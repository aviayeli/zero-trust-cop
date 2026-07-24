"""Tests for engine.board in_bounds validation."""

from engine.board import Board
from engine.config import load_config


def test_in_bounds_valid_corners():
    """Test in_bounds returns True for all four corners."""
    config = load_config("config/game.json")
    board = Board(config)

    assert board.in_bounds((0, 0)) is True
    assert board.in_bounds((0, 6)) is True
    assert board.in_bounds((6, 0)) is True
    assert board.in_bounds((6, 6)) is True


def test_in_bounds_valid_center():
    """Test in_bounds returns True for the center cell."""
    config = load_config("config/game.json")
    board = Board(config)

    assert board.in_bounds((3, 3)) is True


def test_in_bounds_invalid_negatives():
    """Test in_bounds returns False for negative coordinates."""
    config = load_config("config/game.json")
    board = Board(config)

    assert board.in_bounds((-1, 0)) is False
    assert board.in_bounds((0, -1)) is False
    assert board.in_bounds((-1, -1)) is False


def test_in_bounds_invalid_out_of_bounds():
    """Test in_bounds returns False for coordinates >= grid_size."""
    config = load_config("config/game.json")
    board = Board(config)

    assert board.in_bounds((7, 0)) is False
    assert board.in_bounds((0, 7)) is False
    assert board.in_bounds((7, 7)) is False
    assert board.in_bounds((8, 8)) is False
