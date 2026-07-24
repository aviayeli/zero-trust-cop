"""Tests for engine.board barrier placement, limits, and ordering."""

import pytest
from engine.board import Board
from engine.config import load_config
from engine.errors import IllegalBarrierPlacementError, BarrierLimitError


def test_is_barrier_before_placement():
    """Test is_barrier returns False before any placement."""
    config = load_config("config/game.json")
    board = Board(config)

    assert board.is_barrier((2, 2)) is False
    assert board.is_barrier((0, 0)) is False
    assert board.is_barrier((6, 6)) is False


def test_place_barrier_single():
    """Test placing a single barrier."""
    config = load_config("config/game.json")
    board = Board(config)

    board.place_barrier((2, 2))
    assert board.is_barrier((2, 2)) is True
    assert board.barrier_count == 1


def test_barrier_count_increments():
    """Test barrier_count increments correctly with sequential placements."""
    config = load_config("config/game.json")
    board = Board(config)

    assert board.barrier_count == 0

    board.place_barrier((0, 1))
    assert board.barrier_count == 1

    board.place_barrier((1, 1))
    assert board.barrier_count == 2

    board.place_barrier((2, 2))
    assert board.barrier_count == 3


def test_place_barrier_occupied_cell_raises_error():
    """Test placing barrier on an occupied cell raises IllegalBarrierPlacementError."""
    config = load_config("config/game.json")
    board = Board(config)

    occupied = [(0, 0), (3, 3)]

    with pytest.raises(IllegalBarrierPlacementError):
        board.place_barrier((0, 0), occupied=occupied)

    with pytest.raises(IllegalBarrierPlacementError):
        board.place_barrier((3, 3), occupied=occupied)


def test_place_barrier_occupied_empty_list():
    """Test placing barrier with empty occupied list succeeds."""
    config = load_config("config/game.json")
    board = Board(config)

    board.place_barrier((2, 2), occupied=[])
    assert board.is_barrier((2, 2)) is True


def test_barrier_limit_enforcement():
    """Test that barrier limit is enforced at max_barriers."""
    config = load_config("config/game.json")
    board = Board(config)

    # Generate 14 distinct cells and place them successfully
    cells_to_place = []
    for r in range(config.grid_size):
        for c in range(config.grid_size):
            if len(cells_to_place) < config.max_barriers:
                cells_to_place.append((r, c))

    # Place the first 14 barriers
    for cell in cells_to_place:
        board.place_barrier(cell)

    assert board.barrier_count == 14

    # Try to place a 15th barrier (should fail)
    # Find a cell that hasn't been used
    used_cells = set(cells_to_place)
    cell_to_fail = None
    for r in range(config.grid_size):
        for c in range(config.grid_size):
            if (r, c) not in used_cells:
                cell_to_fail = (r, c)
                break
        if cell_to_fail:
            break

    assert cell_to_fail is not None

    with pytest.raises(BarrierLimitError):
        board.place_barrier(cell_to_fail)

    # Verify barrier_count stays at 14 after failed placement
    assert board.barrier_count == 14


def test_barrier_placement_order_matters():
    """Test that occupied check happens before limit check."""
    config = load_config("config/game.json")
    board = Board(config)

    # Fill the board to the limit
    cells = [(r, c) for r in range(config.grid_size) for c in range(config.grid_size)][:config.max_barriers]
    for cell in cells:
        board.place_barrier(cell)

    # Try to place on an occupied cell when limit is reached
    # The occupied error should be raised, not the limit error
    occupied = [(cells[0][0], cells[0][1])]

    with pytest.raises(IllegalBarrierPlacementError):
        board.place_barrier(cells[0], occupied=occupied)
