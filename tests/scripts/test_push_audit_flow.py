"""The push loop's audit and its failure modes (PRD_09 FR3, FR4).

The lockstep ordering lives in `test_push_match_loop.py`; this file covers
what happens at the end of a sub-game and when the opponent stops answering.
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


async def _never_terminates(step, ours, theirs):
    return {"terminated": False}


def _run(max_steps=3, their_moves=None, terminate_at=None):
    peer = FakePeer()
    store = PushStore()
    client = PushClient(peer, role="police")
    their_moves = their_moves or dict.fromkeys(range(1, max_steps + 1), "MOVE:S")
    seen = []

    def choose(step):
        return "MOVE:N", f"hint {step}", "truth"

    async def advance(step, ours, theirs):
        seen.append((step, ours, theirs))
        return {"terminated": terminate_at is not None and step >= terminate_at,
                "terminal_reason": "capture" if terminate_at else None}

    summary = asyncio.run(play_sub_game(
        client, store, choose=choose, advance=advance,
        max_steps=max_steps, wait=_scripted_opponent(store, their_moves),
    ))
    return peer, client, summary, seen


def test_the_audit_is_sent_once_at_the_end_with_every_record():
    peer, client, _, _ = _run(max_steps=3)

    audits = [k["payload"] for n, k in peer.calls if n == "submit_audit"]

    assert len(audits) == 1
    assert peer.names()[-1] == "submit_audit"
    assert len(audits[0]["records"]) == 3
    assert client.buffered == []


def test_the_audit_claims_our_own_result():
    """A claim, not a verdict: their re-hash settles the sub-game."""
    peer, _, summary, _ = _run(max_steps=9, terminate_at=2)

    claim = [k["payload"] for n, k in peer.calls if n == "submit_audit"][0]["result_claim"]

    assert claim == {"outcome": "capture", "steps": 2}
    assert summary["result_claim"] == claim


def test_every_audit_entry_reproduces_the_commit_we_sent():
    """Our own chain stays auditable even though theirs may not be."""
    peer, _, _, _ = _run(max_steps=3)

    sent = [k["h_commit"] for n, k in peer.calls if n == "receive_commit"]
    records = [k["payload"] for n, k in peer.calls if n == "submit_audit"][0]["records"]

    assert [r["commit"] for r in records] == sent
    for record in records:
        assert interop.commit(record["payload"], record["nonce"]) == record["commit"]


def test_a_stalled_opponent_does_not_hang_forever():
    """If their step never lands we must fail loudly, not block a match."""
    peer = FakePeer()
    store = PushStore()
    client = PushClient(peer, role="police")

    async def never():
        return None

    with pytest.raises(TimeoutError, match="step 1"):
        asyncio.run(play_sub_game(
            client, store, choose=lambda s: ("MOVE:N", "", "truth"),
            advance=_never_terminates,
            max_steps=2, wait=never, max_polls=3,
        ))


def test_nonces_are_unpredictable_and_never_repeat():
    """The nonce is the only thing hiding our move: the move set has five
    elements, so a derivable nonce lets the opponent brute-force our
    commitment before we reveal it."""
    peer, _, _, _ = _run(max_steps=3)
    records = [k["payload"] for n, k in peer.calls if n == "submit_audit"][0]["records"]
    nonces = [e["nonce"] for e in records]

    assert len(set(nonces)) == len(nonces)
    for nonce in nonces:
        assert len(nonce) == 32
        int(nonce, 16)

    again = [e["nonce"] for e in
             [k["payload"] for n, k in _run(max_steps=3)[0].calls
              if n == "submit_audit"][0]["records"]]
    assert not set(nonces) & set(again), "nonces repeated across sub-games"
