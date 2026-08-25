"""Tests for build_observation and build_move_waiting functions."""

from mcp_server.observations import build_move_waiting, build_observation

# --- build_observation -------------------------------------------------


def test_build_observation_cop_own_view(make_match_state, make_config):
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
        # Stated so a peer can refuse a mirrored engine before turn 0.
        "axis_origin_corner": "top-left",
        "axis_start_index": 0,
        # ...and the rules it would otherwise disagree about silently.
        "max_moves": 35,
        "scoring": {
            "capture_cop": 20, "capture_thief": 5, "survival_cop": 5,
            "survival_thief": 10, "tie_score": 2, "technical_loss": 0,
        },
    }


def test_build_observation_thief_own_view(make_match_state, make_config):
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
        # Stated so a peer can refuse a mirrored engine before turn 0.
        "axis_origin_corner": "top-left",
        "axis_start_index": 0,
        # ...and the rules it would otherwise disagree about silently.
        "max_moves": 35,
        "scoring": {
            "capture_cop": 20, "capture_thief": 5, "survival_cop": 5,
            "survival_thief": 10, "tie_score": 2, "technical_loss": 0,
        },
    }


def test_build_observation_excludes_opponent_position_for_cop(make_match_state, make_config):
    match_state = make_match_state(cop_position=(0, 0), thief_position=(3, 4))
    config = make_config(grid_size=7)

    result = build_observation(match_state, config, "cop")

    assert (3, 4) not in result.values()
    assert "thief_position" not in result
    assert "opponent_position" not in result


def test_build_observation_excludes_opponent_position_for_thief(make_match_state, make_config):
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


def test_build_move_waiting_default_opponent_is_unchanged():
    assert build_move_waiting("cop")["message"] == "action buffered; waiting for thief"
