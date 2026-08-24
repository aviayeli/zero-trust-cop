"""What a finished sub-game hands back, and what it says while it runs.

Split from `test_claims_match_loop.py` at the 150-line limit. That module
pins the loop's mechanics; this pins its OUTPUT — the sealed chain the
artifacts are written from, and the per-step progress line.

Both exist because of the same gap: four aborted series against rstabcde were
argued from the opponent's inbound traffic alone. The chain was handed to
`audit()` and cleared, and the runner printed nothing until a series ended,
which for a series that never ends is nothing at all.
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


def test_the_summary_carries_the_chain_the_artifacts_need(config):
    """The sealed chain is handed to `audit()` and the buffer is cleared, so
    a series used to end holding nothing but numbers — there was no log to
    write. The artifact the grader reads has to be replayable, which means
    every payload, nonce and digest we sealed, and every turn they pushed.
    """
    _, _, summary = _play(config, max_steps=3)

    assert [r["payload"]["step"] for r in summary["our_chain"]] == [1, 2, 3]
    assert all({"payload", "nonce", "commit"} <= set(r) for r in summary["our_chain"])
    assert [t["step"] for t in summary["their_turns"]] == [1, 2, 3]


def test_the_chain_survives_the_audit_that_consumes_it(config):
    """`TurnClient.audit` clears its buffer by design — a second audit must
    not re-assert a sub-game. The summary keeps its own copy."""
    _, _, summary = _play(config, max_steps=2)

    assert len(summary["our_chain"]) == 2


def test_a_chain_entry_rehashes_to_the_digest_we_pushed(config):
    """What makes the log evidence rather than a transcript."""
    from mcp_server import interop

    peer, _, summary = _play(config, max_steps=2)

    pushed = [turn["commit"] for turn in peer.turns()]
    for record, commit in zip(summary["our_chain"], pushed):
        assert interop.commit(record["payload"], record["nonce"]) == commit


def test_the_loop_reports_each_step_as_it_happens(config):
    """Our side of the timeline, live.

    Four aborted series against rstabcde were argued from THEIR inbound
    traffic alone — we could see every turn they pushed and nothing we sent,
    so "their sub-game timed out waiting for us" and "they restarted" fit the
    same evidence and neither side could settle it. The runner printed
    nothing until the series ended, which for a series that never ends is
    nothing at all.
    """
    seen = []
    _play(config, max_steps=3, progress=seen.append)

    assert [p["step"] for p in seen] == [1, 2, 3]
    assert [p["phase"] for p in seen] == ["pushed"] * 3


def test_the_report_says_when_THEIR_step_landed(config):
    """The gap between our push and their reply is the number in dispute."""
    seen = []
    _play(config, max_steps=2, progress=seen.append,
          scripted={s: _their_turn(s) for s in (1, 2)})

    assert all("theirs" in p for p in seen)


def test_a_loop_with_no_reporter_still_plays(config):
    """Progress is diagnostics, never a dependency."""
    _, _, summary = _play(config, max_steps=2)

    assert summary["steps"] == 2
