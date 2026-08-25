"""Tests for engine.resolver capture detection and turn resolution (T5-T11)."""

from engine.actions import Action
from engine.player import PlayerState
from engine.resolver import resolve_turn


def test_t5_same_cell_capture(make_board):
    """Both agents move into the same cell -> captured."""
    board = make_board()
    cop_state = PlayerState((2, 2), "cop")
    thief_state = PlayerState((2, 4), "thief")

    result = resolve_turn(board, cop_state, thief_state, Action.E, Action.W)

    assert result.cop_position == (2, 3)
    assert result.thief_position == (2, 3)
    assert result.captured is True


def test_t6_swap_cross_capture(make_board):
    """Agents swap cells (cross paths) -> captured."""
    board = make_board()
    cop_state = PlayerState((2, 2), "cop")
    thief_state = PlayerState((2, 3), "thief")

    result = resolve_turn(board, cop_state, thief_state, Action.E, Action.W)

    assert result.cop_position == (2, 3)
    assert result.thief_position == (2, 2)
    assert result.captured is True


def test_t7_near_miss_follow_not_swap(make_board):
    """Cop enters thief's vacated cell, but thief also moved on -> not a swap."""
    board = make_board()
    cop_state = PlayerState((2, 2), "cop")
    thief_state = PlayerState((2, 3), "thief")

    result = resolve_turn(board, cop_state, thief_state, Action.E, Action.E)

    assert result.cop_position == (2, 3)
    assert result.thief_position == (2, 4)
    assert result.captured is False


def test_t8_resolution_order_capture_on_resolved_positions(make_board):
    """Capture is detected on resolved STAY position, not the intended off-grid one."""
    board = make_board()
    cop_state = PlayerState((0, 0), "cop")
    thief_state = PlayerState((1, 0), "thief")

    result = resolve_turn(board, cop_state, thief_state, Action.N, Action.N)

    assert result.cop_position == (0, 0)
    assert result.thief_position == (0, 0)
    assert result.captured is True


def test_t9_resolve_turn_does_not_mutate_states(make_board):
    """resolve_turn must not mutate the passed-in PlayerState objects."""
    board = make_board()
    cop_state = PlayerState((0, 0), "cop")
    thief_state = PlayerState((6, 6), "thief")

    resolve_turn(board, cop_state, thief_state, Action.E, Action.W)

    assert cop_state.position == (0, 0)
    assert thief_state.position == (6, 6)


def test_t10_stay_actions_no_movement_no_capture(make_board):
    """Both agents STAY; no movement, no capture."""
    board = make_board()
    cop_state = PlayerState((0, 0), "cop")
    thief_state = PlayerState((6, 6), "thief")

    result = resolve_turn(board, cop_state, thief_state, Action.STAY, Action.STAY)

    assert result.cop_position == (0, 0)
    assert result.thief_position == (6, 6)
    assert result.captured is False


def test_t11_cop_into_barrier_stays(make_board):
    """Cop's move into a barrier resolves to STAY; thief moves normally."""
    board = make_board()
    board.place_barrier((0, 1))
    cop_state = PlayerState((0, 0), "cop")
    thief_state = PlayerState((6, 6), "thief")

    result = resolve_turn(board, cop_state, thief_state, Action.E, Action.W)

    assert result.cop_position == (0, 0)
    assert result.thief_position == (6, 5)
    assert result.captured is False
