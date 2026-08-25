"""Tests for engine.game_loop stepping, capture, and termination behaviors."""

from engine.actions import parse_action
from engine.board import Board
from engine.config import load_config
from engine.game_loop import GameEpisode
from engine.player import PlayerState
from engine.resolver import resolve_turn


def test_one_valid_step_advances_turn_count_and_history(make_episode):
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


def test_capture_terminates_episode(make_episode):
    """A capture in a single step sets captured True and terminates the episode."""
    ep = make_episode()
    ep.cop_state.position = (2, 2)
    ep.thief_state.position = (2, 4)

    result = ep.step("E", "W")

    assert result.captured is True
    assert ep.is_terminated is True


def test_no_mutation_after_termination(make_episode):
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


def test_step_after_termination_with_empty_history_returns_none(make_episode):
    """If terminated with no history (edge case), step() returns None without mutating."""
    ep = make_episode()
    ep.is_terminated = True

    result = ep.step("N", "S")

    assert result is None
    assert ep.turn_count == 0
    assert ep.history == []


def test_max_moves_termination_timing(make_episode):
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
