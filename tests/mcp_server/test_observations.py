"""Tests for mcp_server.observations — five pure view-shaping functions.

These tests use duck-typed stubs (SimpleNamespace) for the not-yet-built
MatchState and TurnResult so observations.py can be built and verified
before match_state.py exists, per TODO_02 Task 2.
"""

from types import SimpleNamespace

from mcp_server.observations import (
    build_move_error,
    build_move_resolved,
    build_move_waiting,
    build_observation,
    build_status,
)


def make_match_state(
    turn_count=4,
    is_terminated=False,
    cop_position=(0, 0),
    thief_position=(3, 4),
    barrier_count=3,
    pending_roles=None,
    terminal_reason=None,
):
    return SimpleNamespace(
        turn_count=turn_count,
        is_terminated=is_terminated,
        cop_position=cop_position,
        thief_position=thief_position,
        barrier_count=barrier_count,
        pending_roles=pending_roles if pending_roles is not None else [],
        terminal_reason=terminal_reason,
    )


def make_config(grid_size=7):
    return SimpleNamespace(grid_size=grid_size)


def make_turn_result(cop_position=(1, 0), thief_position=(3, 4), captured=False):
    return SimpleNamespace(
        cop_position=cop_position,
        thief_position=thief_position,
        captured=captured,
    )


# --- build_observation -------------------------------------------------


def test_build_observation_cop_own_view():
    match_state = make_match_state(
        turn_count=4,
        is_terminated=False,
        cop_position=(0, 0),
        thief_position=(3, 4),
        barrier_count=3,
    )
    config = make_config(grid_size=7)

    result = build_observation(match_state, config, "cop")

    assert result == {
        "role": "cop",
        "position": (0, 0),
        "turn_count": 4,
        "is_terminated": False,
        "grid_size": 7,
        "barrier_count": 3,
    }


def test_build_observation_thief_own_view():
    match_state = make_match_state(
        turn_count=4,
        is_terminated=False,
        cop_position=(0, 0),
        thief_position=(3, 4),
        barrier_count=3,
    )
    config = make_config(grid_size=7)

    result = build_observation(match_state, config, "thief")

    assert result == {
        "role": "thief",
        "position": (3, 4),
        "turn_count": 4,
        "is_terminated": False,
        "grid_size": 7,
        "barrier_count": 3,
    }


def test_build_observation_excludes_opponent_position_for_cop():
    match_state = make_match_state(cop_position=(0, 0), thief_position=(3, 4))
    config = make_config(grid_size=7)

    result = build_observation(match_state, config, "cop")

    assert (3, 4) not in result.values()
    assert "thief_position" not in result
    assert "opponent_position" not in result


def test_build_observation_excludes_opponent_position_for_thief():
    match_state = make_match_state(cop_position=(0, 0), thief_position=(3, 4))
    config = make_config(grid_size=7)

    result = build_observation(match_state, config, "thief")

    assert (0, 0) not in result.values()
    assert "cop_position" not in result
    assert "opponent_position" not in result


# --- build_move_waiting --------------------------------------------------


def test_build_move_waiting_cop():
    result = build_move_waiting("cop")

    assert result == {
        "status": "waiting",
        "role": "cop",
        "message": "action buffered; waiting for thief",
    }


def test_build_move_waiting_thief():
    result = build_move_waiting("thief")

    assert result == {
        "status": "waiting",
        "role": "thief",
        "message": "action buffered; waiting for cop",
    }


# --- build_move_resolved --------------------------------------------------


def test_build_move_resolved_not_terminated():
    match_state = make_match_state(
        turn_count=5,
        is_terminated=False,
        terminal_reason=None,
    )
    result_obj = make_turn_result(cop_position=(1, 0), thief_position=(3, 4), captured=False)

    result = build_move_resolved(match_state, result_obj, "thief")

    assert result == {
        "status": "resolved",
        "role": "thief",
        "cop_position": (1, 0),
        "thief_position": (3, 4),
        "captured": False,
        "turn_count": 5,
        "is_terminated": False,
        "terminal_reason": None,
    }


def test_build_move_resolved_captured_terminal():
    match_state = make_match_state(
        turn_count=12,
        is_terminated=True,
        terminal_reason="capture",
    )
    result_obj = make_turn_result(cop_position=(2, 2), thief_position=(2, 2), captured=True)

    result = build_move_resolved(match_state, result_obj, "cop")

    assert result == {
        "status": "resolved",
        "role": "cop",
        "cop_position": (2, 2),
        "thief_position": (2, 2),
        "captured": True,
        "turn_count": 12,
        "is_terminated": True,
        "terminal_reason": "capture",
    }


# --- build_move_error --------------------------------------------------


def test_build_move_error_invalid_role():
    result = build_move_error("invalid_role")

    assert result["error"] == "invalid_role"
    assert isinstance(result["message"], str)
    assert set(result.keys()) == {"error", "message"}


def test_build_move_error_invalid_direction():
    result = build_move_error("invalid_direction")

    assert result["error"] == "invalid_direction"
    assert isinstance(result["message"], str)
    assert set(result.keys()) == {"error", "message"}


def test_build_move_error_already_submitted():
    result = build_move_error("already_submitted")

    assert result["error"] == "already_submitted"
    assert isinstance(result["message"], str)
    assert set(result.keys()) == {"error", "message"}


# --- build_status --------------------------------------------------


def test_build_status_mid_match():
    match_state = make_match_state(
        turn_count=5,
        is_terminated=False,
        pending_roles=["cop"],
        terminal_reason=None,
    )

    result = build_status(match_state)

    assert result == {
        "turn_count": 5,
        "is_terminated": False,
        "pending_roles": ["cop"],
        "terminal_reason": None,
    }


def test_build_status_terminated_by_capture():
    match_state = make_match_state(
        turn_count=12,
        is_terminated=True,
        pending_roles=[],
        terminal_reason="capture",
    )

    result = build_status(match_state)

    assert result == {
        "turn_count": 12,
        "is_terminated": True,
        "pending_roles": [],
        "terminal_reason": "capture",
    }


def test_build_status_terminated_by_max_moves():
    match_state = make_match_state(
        turn_count=35,
        is_terminated=True,
        pending_roles=[],
        terminal_reason="max_moves_reached",
    )

    result = build_status(match_state)

    assert result == {
        "turn_count": 35,
        "is_terminated": True,
        "pending_roles": [],
        "terminal_reason": "max_moves_reached",
    }


def test_build_status_no_scoring_fields():
    match_state = make_match_state()

    result = build_status(match_state)

    assert set(result.keys()) == {
        "turn_count",
        "is_terminated",
        "pending_roles",
        "terminal_reason",
    }
