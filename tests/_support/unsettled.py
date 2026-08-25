"""Doubles for a sub-game whose closing audit fails (PRD_13).

Two modules drive the same scenario -- one asks whether the sub-game survives
its own audit, the other whether it can ever be mistaken for a settled one --
and a double copied into both is a double that drifts between them.

Lives under `tests/_support` because `pythonpath` names that directory; a
`tests/scripts` package would collide with the `scripts` package in `src`.
"""

import asyncio

import pytest

from engine.config import load_config
from scripts.claims_match_loop import play_sub_game


class Client:
    """A TurnClient whose audit does whatever the test needs."""

    def __init__(self, inbox, audit_error=None):
        self.inbox = inbox
        self.audit_error = audit_error
        self.records = [{"payload": {"step": 1}, "nonce": "n", "commit": "c"}]
        self.audits = 0

    def seal(self, payload):
        return "d" * 64, "nonce"

    async def turn(self, message):
        # Their answer for this step is already waiting when we poll.
        self.inbox.append({"step": message["step"], "sender": "thief",
                           "hint": "", "smell_grid": {}, "commit": "c" * 64,
                           "timestamp": "2026-08-25T00:00:00Z"})
        return {"status": "accepted"}

    async def audit(self, result_claim):
        self.audits += 1
        if self.audit_error is not None:
            raise self.audit_error
        return {"status": "accepted", "records_verified": 1}


class Side:
    """The minimum of `Side` that the loop touches."""

    sender = "police"
    captured_them = False
    caught = False

    def __init__(self, config):
        self.config = config

    def walk(self, move):
        return (3, 3)

    def smell_grid(self):
        return {}

    def extras(self, step):
        return {}

    def read(self, turn):
        pass


@pytest.fixture
def config():
    return load_config("config/game.json")


async def _nothing():
    return None


def play_closing(config, audit_error=None, steps=2):
    """Play a short sub-game and return ``(client, summary)``."""
    inbox = []
    client = Client(inbox, audit_error)
    summary = asyncio.run(play_sub_game(
        client, inbox, Side(config),
        choose=lambda step: ("S", "south", "honest"),
        barriers=[], max_steps=steps, wait=_nothing, max_polls=3))
    return client, summary


def unsettled(config):
    """One summary from a sub-game whose audit could not be delivered."""
    _, summary = play_closing(config, RuntimeError("502 Bad Gateway"))
    return summary


def as_result(summary):
    """Build the series result a single unsettled sub-game produces."""
    from scripts.reference_artifacts import build_result

    return build_result({"game_uid": "u", "game_id": "a-vs-b"},
                        [dict(summary, sub_game=1, role="police")], "a")
