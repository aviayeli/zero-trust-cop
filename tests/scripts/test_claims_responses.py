"""What we do with the answer to a push (PRD_10 10.5).

Split from `test_claims_guards.py` at the 150-line limit. That module pins
the INBOX guard — whose turn may satisfy a wait. This one pins the RESPONSE
guard: what the opponent said when we pushed.

The loop used to discard it. A peer refusing every turn therefore looked
exactly like a peer that was merely quiet, and we waited out the whole poll
budget instead of reporting the reason they had already handed us.

Only an EXPLICIT no counts. ali-ahm1 answers `{"accepted": true}` with no
`status` at all, so treating an unfamiliar shape as a refusal would stall a
healthy series — the opposite failure, and the more expensive one.
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
        return [k["message"] for n, k in self.calls if n == "receive_turn"]

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


def test_a_refused_turn_is_raised_not_discarded(config):
    """The loop threw the push response away, so a peer refusing every turn
    looked identical to a peer that was merely quiet — and we sat waiting.
    """
    class Refusing(FakePeer):
        async def __call__(self, tool, **kwargs):
            self.calls.append((tool, kwargs))
            if tool == "receive_turn":
                return {"status": "refused", "reason": "timestamp: required non-empty str"}
            return {"status": "accepted"}

    peer, inbox = Refusing(), []
    side = Side(config, Board(config), "police")
    client = TurnClient(peer, sender="police")

    with pytest.raises(RuntimeError, match="timestamp: required non-empty str"):
        asyncio.run(play_sub_game(
            client, inbox, side, choose=lambda step: ("MOVE:STAY", "h", "truth"),
            barriers=(), max_steps=2, wait=_delivering(inbox, {}), max_polls=2))


def test_an_acceptance_in_their_spelling_is_not_read_as_a_refusal(config):
    """ali-ahm1 answers `{"accepted": true}` with no `status`. Only an
    EXPLICIT no is a refusal; an unfamiliar shape is not."""
    class Theirs(FakePeer):
        async def __call__(self, tool, **kwargs):
            self.calls.append((tool, kwargs))
            if tool == "receive_turn":
                ours = kwargs["message"]
                inbox_ref.append({
                    "step": ours["step"], "sender": "thief", "hint": "",
                    "smell_grid": {}, "commit": "b" * 64,
                    "timestamp": "2026-08-24T00:00:00Z"})
            return {"accepted": True}

    inbox_ref = []
    side = Side(config, Board(config), "police")
    summary = asyncio.run(play_sub_game(
        TurnClient(Theirs(), sender="police"), inbox_ref, side,
        choose=lambda step: ("MOVE:STAY", "h", "truth"), barriers=(),
        max_steps=2, wait=_delivering(inbox_ref, {}), max_polls=3))

    assert summary["steps"] == 2
