"""Tests for engine.game_loop reset and malformed-token behaviors."""

import pytest

from engine.config import load_config
from engine.errors import InvalidActionError
from engine.game_loop import GameEpisode


def test_reset_initializes_state():
    """reset() seeds tuple positions, zero turn count, not terminated."""
    config = load_config("config/game.json")
    ep = GameEpisode(config)

    assert ep.cop_state.position == tuple(config.cop_start)
    assert ep.cop_state.position == (0, 0)
    assert ep.thief_state.position == tuple(config.thief_start)
    assert ep.thief_state.position == (3, 3)
    assert ep.turn_count == 0
    assert ep.is_terminated is False
    assert ep.history == []


def test_reset_can_restart_after_steps(make_episode):
    """Calling reset() again restores the episode to its initial state."""
    ep = make_episode()
    ep.step("E", "W")
    assert ep.turn_count == 1

    ep.reset()

    assert ep.cop_state.position == (0, 0)
    assert ep.thief_state.position == (3, 3)
    assert ep.turn_count == 0
    assert ep.is_terminated is False
    assert ep.history == []


def test_malformed_cop_token_raises_and_does_not_mutate(make_episode):
    """Bad cop token raises InvalidActionError; no state mutation occurs."""
    ep = make_episode()

    with pytest.raises(InvalidActionError):
        ep.step("BOGUS", "STAY")

    assert ep.turn_count == 0
    assert ep.history == []
    assert ep.cop_state.position == (0, 0)
    assert ep.thief_state.position == (3, 3)
    assert ep.is_terminated is False


def test_malformed_thief_token_raises_and_does_not_mutate(make_episode):
    """Bad thief token raises InvalidActionError; no state mutation occurs."""
    ep = make_episode()

    with pytest.raises(InvalidActionError):
        ep.step("STAY", "NOPE")

    assert ep.turn_count == 0
    assert ep.history == []
    assert ep.cop_state.position == (0, 0)
    assert ep.thief_state.position == (3, 3)
    assert ep.is_terminated is False
