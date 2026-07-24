"""Tests for engine.game_loop module (episode orchestrator, FR6/FR7)."""

import pytest

from engine.actions import Action, parse_action
from engine.board import Board
from engine.config import load_config
from engine.errors import InvalidActionError
from engine.player import PlayerState
from engine.resolver import resolve_turn
from engine.game_loop import GameEpisode


def make_episode():
    """Build a fresh GameEpisode from the game config."""
    config = load_config("config/game.json")
    return GameEpisode(config)


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


def test_reset_can_restart_after_steps():
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


def test_malformed_cop_token_raises_and_does_not_mutate():
    """Bad cop token raises InvalidActionError; no state mutation occurs."""
    ep = make_episode()

    with pytest.raises(InvalidActionError):
        ep.step("BOGUS", "STAY")

    assert ep.turn_count == 0
    assert ep.history == []
    assert ep.cop_state.position == (0, 0)
    assert ep.thief_state.position == (3, 3)
    assert ep.is_terminated is False


def test_malformed_thief_token_raises_and_does_not_mutate():
    """Bad thief token raises InvalidActionError; no state mutation occurs."""
    ep = make_episode()

    with pytest.raises(InvalidActionError):
        ep.step("STAY", "NOPE")

    assert ep.turn_count == 0
    assert ep.history == []
    assert ep.cop_state.position == (0, 0)
    assert ep.thief_state.position == (3, 3)
    assert ep.is_terminated is False


def test_one_valid_step_advances_turn_count_and_history():
    """A single valid step increments turn_count and appends to history."""
    ep = make_episode()

    ep.step("STAY", "STAY")

    assert ep.turn_count == 1
    assert len(ep.history) == 1


def test_step_matches_independent_resolve_turn():
    """episode.step(...) result equals an independently computed resolve_turn result."""
    config = load_config("config/game.json")
    ep = GameEpisode(config)

    board = Board(config)
    cop_state = PlayerState(tuple(config.cop_start), "cop")
    thief_state = PlayerState(tuple(config.thief_start), "thief")
    cop_action = parse_action("S")
    thief_action = parse_action("N")
    expected = resolve_turn(board, cop_state, thief_state, cop_action, thief_action)

    result = ep.step("S", "N")

    assert result == expected


def test_capture_terminates_episode():
    """A capture in a single step sets captured True and terminates the episode."""
    ep = make_episode()
    ep.cop_state.position = (2, 2)
    ep.thief_state.position = (2, 4)

    result = ep.step("E", "W")

    assert result.captured is True
    assert ep.is_terminated is True


def test_no_mutation_after_termination():
    """After termination, a further step() is a harmless no-op."""
    ep = make_episode()
    ep.cop_state.position = (2, 2)
    ep.thief_state.position = (2, 4)

    ep.step("E", "W")
    assert ep.is_terminated is True

    turn_count_before = ep.turn_count
    cop_pos_before = ep.cop_state.position
    thief_pos_before = ep.thief_state.position
    history_len_before = len(ep.history)
    last_result_before = ep.history[-1].result

    result = ep.step("N", "S")

    assert result == last_result_before
    assert ep.turn_count == turn_count_before
    assert ep.cop_state.position == cop_pos_before
    assert ep.thief_state.position == thief_pos_before
    assert len(ep.history) == history_len_before


def test_step_after_termination_with_empty_history_returns_none():
    """If terminated with no history (edge case), step() returns None without mutating."""
    ep = make_episode()
    ep.is_terminated = True

    result = ep.step("N", "S")

    assert result is None
    assert ep.turn_count == 0
    assert ep.history == []


def test_max_moves_termination_timing():
    """From default starts, STAY/STAY never collides; termination fires exactly at move 35."""
    ep = make_episode()

    for i in range(1, 35):
        result = ep.step("STAY", "STAY")
        assert result.captured is False
        assert ep.is_terminated is False, f"terminated too early at turn {i}"
        assert ep.turn_count == i

    result = ep.step("STAY", "STAY")

    assert ep.turn_count == 35
    assert ep.is_terminated is True
    assert result.captured is False


def test_history_integrity_order_and_contents():
    """History entries record the submitted actions and TurnResult, in order."""
    ep = make_episode()
    sequence = [("S", "N"), ("E", "W"), ("STAY", "STAY")]

    for cop_tok, thief_tok in sequence:
        ep.step(cop_tok, thief_tok)

    assert len(ep.history) == len(sequence)
    for record, (cop_tok, thief_tok) in zip(ep.history, sequence):
        assert record.cop_action == parse_action(cop_tok)
        assert record.thief_action == parse_action(thief_tok)
        assert record.result.cop_position is not None
        assert record.result.thief_position is not None


def test_replay_is_deterministic_fr7():
    """Two fresh episodes replaying the same action sequence produce equal history."""
    config = load_config("config/game.json")
    sequence = [
        ("S", "N"),
        ("E", "W"),
        ("STAY", "STAY"),
        ("S", "N"),
        ("W", "E"),
    ]

    ep1 = GameEpisode(config)
    ep2 = GameEpisode(config)

    ep1.replay(sequence)
    ep2.replay(sequence)

    assert ep1.history == ep2.history
    assert ep1.is_terminated == ep2.is_terminated
    assert ep1.turn_count == ep2.turn_count


def test_replay_resets_before_stepping():
    """replay() resets the episode first, so prior state does not leak in."""
    ep = make_episode()
    ep.step("STAY", "STAY")
    ep.step("STAY", "STAY")
    assert ep.turn_count == 2

    result = ep.replay([("S", "N")])

    assert result is ep
    assert ep.turn_count == 1
    assert len(ep.history) == 1
