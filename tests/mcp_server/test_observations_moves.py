"""Tests for build_move_resolved and build_move_error functions."""

from mcp_server.observations import build_move_error, build_move_resolved


# --- build_move_resolved --------------------------------------------------


def test_build_move_resolved_not_terminated(make_match_state, make_turn_result):
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


def test_build_move_resolved_captured_terminal(make_match_state, make_turn_result):
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
