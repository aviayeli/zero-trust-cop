"""Tests for build_status function."""

from mcp_server.observations import build_status


# --- build_status --------------------------------------------------


def test_build_status_mid_match(make_match_state):
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


def test_build_status_terminated_by_capture(make_match_state):
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


def test_build_status_terminated_by_max_moves(make_match_state):
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


def test_build_status_no_scoring_fields(make_match_state):
    match_state = make_match_state()

    result = build_status(match_state)

    assert set(result.keys()) == {
        "turn_count",
        "is_terminated",
        "pending_roles",
        "terminal_reason",
    }
