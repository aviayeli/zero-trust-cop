"""Rate and peer-isolation tests for opponent-honesty beliefs."""

from dataclasses import replace

from engine.config import load_config
from strategy.belief import BeliefTracker
from strategy.settings import load_strategy_settings


def make_tracker(prior=0.5):
    settings = replace(load_strategy_settings("police"), honesty_prior=prior)
    return BeliefTracker(load_config("config/game.json"), settings)


def test_no_observations_returns_replaced_prior_exactly():
    assert make_tracker(0.25).honesty_rate("thief") == 0.25


def test_unscorable_observations_do_not_move_rate():
    tracker = make_tracker()
    for intent in ("quiet", "no comment", "perhaps"):
        assert tracker.record("thief", intent, "N") == "unscorable"
    assert tracker.honesty_rate("thief") == 0.5


def test_mixed_evidence_excludes_unscorable_entries():
    tracker = make_tracker()
    for intent, move in (("north", "N"), ("west", "W"), ("stay", "STAY")):
        tracker.record("thief", intent, move)
    tracker.record("thief", "north", "S")
    tracker.record("thief", "not saying", "N")
    assert tracker.honesty_rate("thief") == 0.75


def test_peer_records_are_isolated():
    tracker = make_tracker()
    tracker.record("thief", "north", "S")
    assert tracker.honesty_rate("police") == 0.5
