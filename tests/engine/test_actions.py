"""Tests for engine.actions module."""

import pytest
from engine.actions import Action, parse_action, action_delta
from engine.errors import InvalidActionError
from engine.config import load_config


def test_action_enum_members():
    """Test that Action enum has exactly 5 members: N, S, E, W, STAY."""
    members = {member.name for member in Action}
    assert members == {"N", "S", "E", "W", "STAY"}
    assert len(Action) == 5


def test_parse_action_valid_tokens():
    """Test parse_action returns the correct Action for valid tokens."""
    assert parse_action("N") == Action.N
    assert parse_action("S") == Action.S
    assert parse_action("E") == Action.E
    assert parse_action("W") == Action.W
    assert parse_action("STAY") == Action.STAY


def test_parse_action_lowercase_raises_error():
    """Test that parse_action raises InvalidActionError for lowercase input."""
    with pytest.raises(InvalidActionError):
        parse_action("n")


def test_parse_action_invalid_string_raises_error():
    """Test that parse_action raises InvalidActionError for invalid string."""
    with pytest.raises(InvalidActionError):
        parse_action("XYZ")


def test_action_delta_north():
    """Test that action_delta returns correct delta for North."""
    assert action_delta(Action.N) == (-1, 0)


def test_action_delta_south():
    """Test that action_delta returns correct delta for South."""
    assert action_delta(Action.S) == (1, 0)


def test_action_delta_east():
    """Test that action_delta returns correct delta for East."""
    assert action_delta(Action.E) == (0, 1)


def test_action_delta_west():
    """Test that action_delta returns correct delta for West."""
    assert action_delta(Action.W) == (0, -1)


def test_action_delta_stay():
    """Test that action_delta returns correct delta for Stay."""
    assert action_delta(Action.STAY) == (0, 0)


def test_drift_guard_action_order_matches_config():
    """DRIFT-GUARD: Action enum members must match config move_set order."""
    config = load_config("config/game.json")
    action_names = [a.name for a in Action]
    expected_order = config.move_set

    assert action_names == expected_order, (
        f"Action enum order {action_names} does not match "
        f"config move_set {expected_order}"
    )
