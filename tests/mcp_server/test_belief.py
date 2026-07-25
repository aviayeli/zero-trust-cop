"""Direction-matching tests for opponent-honesty beliefs."""


import pytest

from engine.config import load_config
from strategy.belief import BeliefTracker
from strategy.settings import load_strategy_settings


@pytest.fixture
def tracker():
    return BeliefTracker(load_config("config/game.json"), load_strategy_settings("police"))


@pytest.mark.parametrize(
    ("intent", "move", "verdict"),
    [
        ("I will go north", "N", "honest"),
        ("I will go north", "S", "dishonest"),
        ("I have a plan", "N", "unscorable"),
        ("I am heading northern", "N", "honest"),
        ("SNOW", "N", "unscorable"),
        ("NEWS", "N", "unscorable"),
        ("N", "N", "honest"),
        ("go north or west", "W", "honest"),
        ("stay put", "STAY", "honest"),
        ("NORTH", "N", "honest"),
        ("north", "N", "honest"),
    ],
)
def test_record_verdicts(tracker, intent, move, verdict):
    assert tracker.record("thief", intent, move) == verdict


def test_long_intent_naming_correct_direction_is_honest(tracker):
    intent = "I will carefully move north after considering every possibility in detail"
    assert tracker.record("thief", intent, "N") == "honest"


def test_counts_reports_all_verdict_tallies(tracker):
    tracker.record("thief", "north", "N")
    tracker.record("thief", "south", "N")
    tracker.record("thief", "waiting", "N")
    assert tracker.counts("thief") == {
        "honest": 1,
        "dishonest": 1,
        "unscorable": 1,
    }
