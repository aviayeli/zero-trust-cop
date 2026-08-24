"""Driving one sub-game on the push dialect (PRD_09 FR3, TODO 9.4).

The loop is lockstep without a gate: we push our commit and reveal, then wait
for theirs to land in the store their pushes fill. Nothing verifies their
reveal against their commit while this runs -- that is the protocol, and the
audit at the end is where it is meant to be caught.

`step` is a PER-SENDER counter (agreed with ali-ahm1): each side numbers its
own chain 1..max_steps, so `max_steps: 35` means 35 moves EACH.
"""

import asyncio

import pytest

from mcp_server import interop
from mcp_server.push_audit import PushStore
from mcp_server.push_client import PushClient
from scripts.push_match_loop import play_sub_game


class FakePeer:
    def __init__(self):
        self.calls = []

    async def __call__(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return {"status": "accepted"}

    def names(self):
        return [name for name, _ in self.calls]


def _scripted_opponent(store, moves):
    """Their pushes landing in our store, one step per poll."""
    delivered = {"step": 0}

    async def wait():
        delivered["step"] += 1
        step = delivered["step"]
        if step in moves:
            payload = {"step": step, "move": moves[step]}
            store.commits[step] = interop.commit(payload, f"theirs-{step}")
            store.reveals[step] = {"role": "thief", "move": moves[step],
                                   "hint": "", "intent": "truth"}

    return wait


def _run(max_steps=3, their_moves=None, terminate_at=None):
    peer = FakePeer()
    store = PushStore()
    client = PushClient(peer, role="police")
    their_moves = their_moves or {s: "MOVE:S" for s in range(1, max_steps + 1)}
    seen = []

    def choose(step):
        return f"MOVE:N", f"hint {step}", "truth"

    def advance(step, ours, theirs):
        seen.append((step, ours, theirs))
        return {"terminated": terminate_at is not None and step >= terminate_at,
                "terminal_reason": "capture" if terminate_at else None}

    summary = asyncio.run(play_sub_game(
        client, store, choose=choose, advance=advance,
        max_steps=max_steps, wait=_scripted_opponent(store, their_moves),
    ))
    return peer, client, summary, seen


def test_each_step_pushes_a_commit_then_a_reveal():
    peer, _, _, _ = _run(max_steps=2)

    order = [n for n in peer.names() if n != "submit_audit"]

    assert order == ["receive_commit", "receive_reveal",
                     "receive_commit", "receive_reveal"]


def test_the_commit_precedes_the_reveal_at_every_step():
    """Revealing before committing would hand them our move for free."""
    peer, _, _, _ = _run(max_steps=3)

    for name, kwargs in peer.calls:
        if name == "receive_reveal":
            committed = [k["step"] for n, k in peer.calls
                         if n == "receive_commit"
                         and peer.calls.index((n, k)) < peer.calls.index((name, kwargs))]
            assert kwargs["step"] in committed


def test_our_step_counter_is_our_own_and_starts_at_one():
    peer, _, _, _ = _run(max_steps=3)

    steps = [k["step"] for n, k in peer.calls if n == "receive_commit"]

    assert steps == [1, 2, 3]


def test_the_engine_sees_both_moves_each_step():
    _, _, _, seen = _run(max_steps=2, their_moves={1: "MOVE:E", 2: "MOVE:W"})

    assert seen == [(1, "MOVE:N", "MOVE:E"), (2, "MOVE:N", "MOVE:W")]


def test_the_loop_stops_when_the_engine_says_terminated():
    peer, _, summary, seen = _run(max_steps=9, terminate_at=2)

    assert len(seen) == 2
    assert summary["steps"] == 2
    assert summary["terminal_reason"] == "capture"


def test_the_loop_stops_at_max_steps_without_a_terminal():
    _, _, summary, seen = _run(max_steps=3)

    assert len(seen) == 3
    assert summary["steps"] == 3
    assert summary["terminal_reason"] is None
