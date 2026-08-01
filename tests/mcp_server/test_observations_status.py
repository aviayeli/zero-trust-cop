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
        "forfeited_by": [],
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
        "forfeited_by": [],
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
        "forfeited_by": [],
    }


def test_build_status_no_scoring_fields(make_match_state):
    match_state = make_match_state()

    result = build_status(match_state)

    assert set(result.keys()) == {
        "turn_count",
        "is_terminated",
        "pending_roles",
        "terminal_reason",
        "forfeited_by",
    }


def test_build_status_reports_a_forfeit(make_match_state):
    """V5: a technical loss must be visible in the status payload itself."""
    match_state = make_match_state(
        turn_count=3,
        is_terminated=True,
        terminal_reason="technical_loss",
        forfeited_by=["thief"],
    )

    result = build_status(match_state)

    assert result["terminal_reason"] == "technical_loss"
    assert result["forfeited_by"] == ["thief"]
