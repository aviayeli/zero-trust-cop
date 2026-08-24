"""Capture and survival on reference-v3, adjudicated by claim (PRD_10 FR4-FR5).

Split from `test_claims_match_loop.py` at the 150-line limit; the seam is the
subject, not the arithmetic. That module pins the loop's MECHANICS — what is
pushed, what is polled, what stalls. This one pins what ENDS a sub-game, which
on this wire is never a resolver's verdict: the police claims a cell, the
thief answers honestly, and the answer is the police's only notification.

The ordering asserted here is the one a live series would lose silently. A
caught thief that stops before its `claim_response` reaches the wire leaves
the police hunting a thief that already knows it lost, until the step budget
runs out and both sides report a different sub-game.
"""

import asyncio

import pytest

from engine.board import Board
from engine.config import load_config
from mcp_server.claims_side import Side
from mcp_server.turn_client import TurnClient
from scripts.claims_match_loop import play_sub_game


class FakePeer:
    def __init__(self):
        self.calls = []

    async def __call__(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return {"status": "accepted"}

    def turns(self):
        return [kwargs["message"] for name, kwargs in self.calls
                if name == "receive_turn"]

    def names(self):
        return [name for name, _ in self.calls]


@pytest.fixture
def config():
    return load_config("config/game.json")


def _their_turn(step, sender="thief", **extra):
    return dict({
        "step": step, "sender": sender, "hint": f"hint {step}",
        "smell_grid": {"3,3": 0.9}, "commit": "b" * 64,
        "timestamp": "2026-08-24T00:00:00Z",
    }, **extra)


def _delivering(inbox, scripted):
    """Their pushes landing in OUR inbox, one step per poll."""
    delivered = {"step": 0}

    async def wait():
        delivered["step"] += 1
        step = delivered["step"]
        if step in scripted:
            inbox.append(scripted[step])

    return wait


def _play(config, sender="police", max_steps=3, scripted=None, moves="MOVE:STAY",
          observed=None, max_polls=600):
    peer, inbox = FakePeer(), []
    side = Side(config, Board(config), sender)
    if scripted is None:
        scripted = {s: _their_turn(s) for s in range(1, max_steps + 1)}

    def choose(step):
        return moves, f"our hint {step}", "truth"

    summary = asyncio.run(play_sub_game(
        TurnClient(peer, sender=sender), inbox, side, choose=choose,
        barriers=(), max_steps=max_steps, wait=_delivering(inbox, scripted),
        observe=None if observed is None else observed.append,
        max_polls=max_polls,
    ))
    return peer, side, summary


def test_the_police_stops_when_the_thief_answers_caught(config):
    scripted = {
        1: _their_turn(1),
        2: _their_turn(2, claim_response={"claim": [1, 0], "caught": True}),
    }
    _, side, summary = _play(config, sender="police", max_steps=5, scripted=scripted)

    assert side.captured_them is True
    assert summary["terminal_reason"] == "capture"
    assert summary["steps"] == 2


def test_a_caught_thief_gets_its_answer_onto_the_wire_before_stopping(config):
    """The answer is the police's only notification. Stopping first strands it."""
    scripted = {1: _their_turn(1, sender="police",
                               capture_claim=list(config.thief_start))}
    peer, side, summary = _play(config, sender="thief", max_steps=5,
                                scripted=scripted)

    assert side.caught is True
    assert peer.turns()[-1]["claim_response"] == {
        "claim": list(config.thief_start), "caught": True,
    }
    assert summary["terminal_reason"] == "capture"
    assert summary["steps"] == 2


def test_a_claim_on_the_wrong_cell_does_not_end_the_sub_game(config):
    scripted = {s: _their_turn(s, sender="police", capture_claim=[0, 0])
                for s in range(1, 4)}
    _, side, summary = _play(config, sender="thief", max_steps=3, scripted=scripted)

    assert side.caught is False
    assert summary["steps"] == 3
    assert summary["terminal_reason"] == "survival"


def test_the_thief_claims_survival_on_the_last_step(config):
    steps = config.survival_threshold
    peer, _, summary = _play(config, sender="thief", max_steps=steps,
                             scripted={s: _their_turn(s, sender="police")
                                       for s in range(1, steps + 1)})

    assert peer.turns()[-1]["win_claim"] == {"type": "survival"}
    assert summary["terminal_reason"] == "survival"


def test_the_result_claim_is_ours_and_travels_with_the_audit(config):
    peer, _, summary = _play(config, max_steps=2)

    payload = [kwargs["payload"] for name, kwargs in peer.calls
               if name == "submit_audit"][0]
    assert payload["result_claim"] == summary["result_claim"]
    assert payload["result_claim"] == {"outcome": "survival", "steps": 2}
