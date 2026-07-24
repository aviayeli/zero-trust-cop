"""Tests for engine.game_loop history integrity and replay determinism (FR7)."""

from engine.actions import parse_action
from engine.config import load_config
from engine.game_loop import GameEpisode


def test_history_integrity_order_and_contents(make_episode):
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


def test_replay_resets_before_stepping(make_episode):
    """replay() resets the episode first, so prior state does not leak in."""
    ep = make_episode()
    ep.step("STAY", "STAY")
    ep.step("STAY", "STAY")
    assert ep.turn_count == 2

    result = ep.replay([("S", "N")])

    assert result is ep
    assert ep.turn_count == 1
    assert len(ep.history) == 1
