"""One sub-game on reference-v3 (PRD_10 FR2-FR5).

The loop plays on CLAIMS. Nothing here waits for a reveal, because this wire
has none: their turn carries a digest and never a move, so our piece is the
only one we resolve and capture is settled by claim and honest answer.

The property that would silently break a live series: their turn must be
found BY STEP in the inbox `receive_turn` fills. An earlier build appended
inbound turns to a list no code ever read, and the handshake still looked
perfect — two inboxes, one of them a dead end.

What ENDS a sub-game is pinned next door, in `test_claims_capture.py`.
"""

import asyncio

import pytest

from engine.board import Board
from engine.config import load_config
from mcp_server import wire_v3
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
          observed=None, max_polls=600, progress=None):
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
        max_polls=max_polls, progress=progress,
    ))
    return peer, side, summary


def test_every_pushed_turn_is_conformant(config):
    peer, _, _ = _play(config)

    assert peer.turns()
    for turn in peer.turns():
        assert wire_v3.validate_turn_message(turn) == wire_v3.ACCEPT


def test_the_sub_game_closes_with_one_audit_per_step_played(config):
    peer, _, summary = _play(config, max_steps=3)

    assert peer.names() == ["receive_turn"] * 3 + ["submit_audit"]
    assert summary["steps"] == 3


def test_their_turn_is_read_out_of_the_inbox_by_step(config):
    observed = []
    _play(config, max_steps=3, observed=observed)

    assert [turn["step"] for turn in observed] == [1, 2, 3]


def test_a_peer_that_never_sends_is_named_with_the_step_it_stalled_on(config):
    with pytest.raises(TimeoutError, match="never sent step 1"):
        _play(config, max_steps=2, scripted={}, max_polls=3)
