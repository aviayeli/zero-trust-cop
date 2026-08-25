"""The two guards on what the wire said (PRD_10 10.5, 10.12).

Split from `test_claims_match_loop.py` at the 150-line limit. That module
pins the loop's mechanics; this pins the two checks that exist because a live
run failed without them.

Both failures had the same shape — the loop believed something it should have
questioned, and the symptom was silence rather than an error. A self-dial fed
us our own turns and completed a whole sub-game against a mirror. A discarded
push response let a peer refuse every turn while looking merely quiet.
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


def test_our_own_turn_never_satisfies_the_wait(config):
    """A self-dial must fail in one step, not play 35 against a mirror.

    Point `--opponent-url` at our own tunnel and every turn we push lands
    straight back in our own inbox carrying OUR sender. Matching on `step`
    alone consumed it as the opponent's, and a whole sub-game completed —
    audits clean, outcome plausible, opponent never involved. There is no
    legitimate reason for our own turn to be in our own inbox, so this is
    raised at once rather than left to time out five minutes later.
    """
    ours = _their_turn(1, sender="police")

    with pytest.raises(RuntimeError, match="own turn"):
        _play(config, sender="police", max_steps=3, scripted={1: ours},
              max_polls=3)


def test_the_self_dial_error_names_the_cause(config):
    """The operator is holding two URLs that look alike; name which is wrong."""
    with pytest.raises(RuntimeError, match="opponent-url"):
        _play(config, sender="police", max_steps=3,
              scripted={1: _their_turn(1, sender="police")}, max_polls=3)


def test_a_genuine_opponent_turn_is_still_read(config):
    """The guard must not reject the traffic it exists to protect."""
    _, _, summary = _play(config, sender="police", max_steps=2,
                          scripted={s: _their_turn(s, sender="thief")
                                    for s in (1, 2)})

    assert summary["steps"] == 2
