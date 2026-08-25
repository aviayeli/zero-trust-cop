"""Tests for engine.player module."""

from engine.actions import Action
from engine.player import PlayerState, intended_position


def test_player_state_initialization_thief():
    """Test PlayerState initialization with thief role."""
    state = PlayerState((3, 3), "thief")
    assert state.position == (3, 3)
    assert state.role == "thief"


def test_player_state_initialization_cop():
    """Test PlayerState initialization with cop role."""
    state = PlayerState((5, 7), "cop")
    assert state.position == (5, 7)
    assert state.role == "cop"


def test_intended_position_north():
    """Test intended_position for North action."""
    state = PlayerState((3, 3), "cop")
    result = intended_position(state, Action.N)
    assert result == (2, 3)


def test_intended_position_south():
    """Test intended_position for South action."""
    state = PlayerState((3, 3), "cop")
    result = intended_position(state, Action.S)
    assert result == (4, 3)


def test_intended_position_east():
    """Test intended_position for East action."""
    state = PlayerState((3, 3), "cop")
    result = intended_position(state, Action.E)
    assert result == (3, 4)


def test_intended_position_west():
    """Test intended_position for West action."""
    state = PlayerState((3, 3), "cop")
    result = intended_position(state, Action.W)
    assert result == (3, 2)


def test_intended_position_stay():
    """Test intended_position for STAY action returns unchanged position."""
    state = PlayerState((3, 3), "cop")
    result = intended_position(state, Action.STAY)
    assert result == (3, 3)


def test_intended_position_no_bounds_awareness_north():
    """Test intended_position has no bounds awareness (returns out-of-grid coords)."""
    state = PlayerState((0, 0), "cop")
    result = intended_position(state, Action.N)
    assert result == (-1, 0)


def test_intended_position_purity():
    """Test intended_position does not mutate state."""
    original_position = (3, 3)
    state = PlayerState(original_position, "thief")

    # Call intended_position multiple times with different actions
    intended_position(state, Action.N)
    intended_position(state, Action.S)
    intended_position(state, Action.E)
    intended_position(state, Action.W)
    intended_position(state, Action.STAY)

    # State position should remain unchanged
    assert state.position == original_position
    assert state.position == (3, 3)
