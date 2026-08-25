"""Tests for engine.resolver movement resolution (T1-T4)."""

from engine.actions import Action
from engine.player import PlayerState
from engine.resolver import resolve_turn


def test_t1_unobstructed(make_board):
    """Both agents move freely; no capture."""
    board = make_board()
    cop_state = PlayerState((0, 0), "cop")
    thief_state = PlayerState((6, 6), "thief")

    result = resolve_turn(board, cop_state, thief_state, Action.E, Action.W)

    assert result.cop_position == (0, 1)
    assert result.thief_position == (6, 5)
    assert result.captured is False


def test_t2_cop_out_of_bounds_stays_thief_unaffected(make_board):
    """Cop's off-grid move resolves to STAY; thief moves normally."""
    board = make_board()
    cop_state = PlayerState((0, 0), "cop")
    thief_state = PlayerState((3, 3), "thief")

    result = resolve_turn(board, cop_state, thief_state, Action.N, Action.E)

    assert result.cop_position == (0, 0)
    assert result.thief_position == (3, 4)
    assert result.captured is False


def test_t3_thief_into_barrier_stays_cop_unaffected(make_board):
    """Thief's move into a barrier resolves to STAY; cop moves normally."""
    board = make_board()
    board.place_barrier((3, 4))
    cop_state = PlayerState((0, 0), "cop")
    thief_state = PlayerState((3, 3), "thief")

    result = resolve_turn(board, cop_state, thief_state, Action.S, Action.E)

    assert result.thief_position == (3, 3)
    assert result.cop_position == (1, 0)
    assert result.captured is False


def test_t4_both_blocked_both_stay(make_board):
    """Both agents attempt off-grid moves; both resolve to STAY."""
    board = make_board()
    cop_state = PlayerState((0, 0), "cop")
    thief_state = PlayerState((6, 6), "thief")

    result = resolve_turn(board, cop_state, thief_state, Action.N, Action.S)

    assert result.cop_position == (0, 0)
    assert result.thief_position == (6, 6)
    assert result.captured is False
