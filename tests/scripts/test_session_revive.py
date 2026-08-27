"""A dead session must be reopened, not reused (PRD_10 10.30).

`lazy_opponents` cached one session per URL and reused it for the whole
series. Against a single-endpoint opponent that means sub-game 2 rides the
connection sub-game 1 opened — and both opponents we played tonight restart
their process between sub-games, so that connection is dead by the time we
need it. Every run ended the same way: sub-game 1 perfect, sub-game 2 dead on
arrival with a 502 we never even tried to recover from.

Reopening is safe HERE and not in `connect_and_play`: the previous sub-game
is already banked and the new one has pushed no turn, so nothing is replayed.
"""

import asyncio
import contextlib

import pytest

from scripts.reference_dial import lazy_opponents

ENDPOINTS = {"cop": "https://one/mcp", "thief": "https://one/mcp"}


class Restarting:
    """One endpoint whose server dies after the first session's Nth call."""

    def __init__(self, die_after):
        self.opens = 0
        self.die_after = die_after
        self.calls = 0

    @contextlib.asynccontextmanager
    async def open(self, url, config):
        self.opens += 1
        generation = self.opens

        async def call(tool, **kwargs):
            self.calls += 1
            if generation == 1 and self.calls > self.die_after:
                raise RuntimeError("502 Bad Gateway")
            return {"ok": True, "generation": generation}

        yield call


async def _no_wait(_seconds):
    """No real waiting in the suite."""


def _run(peer, body):
    async def go():
        async with lazy_opponents(ENDPOINTS, None, dial=peer.open,
                                  sleep=_no_wait) as reach:
            return await body(reach)
    return asyncio.run(go())


def test_a_healthy_session_is_reused():
    peer = Restarting(die_after=99)

    async def body(reach):
        call = await reach("police")
        await call("negotiate")
        await call("receive_turn")

    _run(peer, body)

    assert peer.opens == 1


def test_a_session_that_died_is_reopened_and_the_call_retried():
    """The whole point: sub-game 2's first call must not be the one that
    kills the series."""
    peer = Restarting(die_after=1)

    async def body(reach):
        call = await reach("police")
        await call("negotiate")          # ok, generation 1
        return await call("negotiate")   # generation 1 is dead now

    result = _run(peer, body)

    assert peer.opens == 2, "a dead session must be replaced"
    assert result["generation"] == 2, "the retry must ride the NEW session"


def test_an_endpoint_that_stays_down_still_raises():
    """Reviving must not loop forever over a peer that is simply gone."""
    class Dead(Restarting):
        @contextlib.asynccontextmanager
        async def open(self, url, config):
            self.opens += 1
            if self.opens > 1:
                raise RuntimeError("502 Bad Gateway")

            async def call(tool, **kwargs):
                raise RuntimeError("502 Bad Gateway")
            yield call

    peer = Dead(die_after=0)

    async def body(reach):
        call = await reach("police")
        return await call("negotiate")

    with pytest.raises(RuntimeError, match="502"):
        _run(peer, body)


# --- the abandoned session (live failure, 2026-08-26) ----------------------


class Tracking(Restarting):
    """Records the ORDER of opens and closes, which is what went wrong.

    `_open` assigned `stacks[url] = sub` over the dead entry without closing
    it. The abandoned session was finalised later, out of band, and anyio
    cancelled whatever task was running at that moment -- which was the very
    task that had opened its replacement. Three live series against ZeroOne0
    died at the sub-game 1 boundary this way, each with

        CancelledError: Cancelled via cancel scope ... by
        <Task pending coro=<<async_generator_athrow without __name__>()>>
    """

    def __init__(self, die_after):
        super().__init__(die_after)
        self.events = []

    @contextlib.asynccontextmanager
    async def open(self, url, config):
        self.opens += 1
        generation = self.opens
        self.events.append(f"open{generation}")

        async def call(tool, **kwargs):
            self.calls += 1
            if generation == 1 and self.calls > self.die_after:
                raise RuntimeError("502 Bad Gateway")
            return {"ok": True, "generation": generation}

        try:
            yield call
        finally:
            self.events.append(f"close{generation}")


def test_a_dead_session_is_closed_before_its_replacement_is_opened():
    peer = Tracking(die_after=1)

    async def body(reach):
        call = await reach("police")
        await call("negotiate")
        await call("negotiate")

    _run(peer, body)

    assert peer.events[:3] == ["open1", "close1", "open2"], (
        f"the dead session must be closed BEFORE the replacement opens, "
        f"or its finaliser cancels the task that opened it: {peer.events}")


def test_no_session_is_left_unclosed_at_the_end():
    """An abandoned session is not merely untidy: it is finalised later, out
    of band, and takes a live task down with it."""
    peer = Tracking(die_after=1)

    async def body(reach):
        call = await reach("police")
        await call("negotiate")
        await call("negotiate")

    _run(peer, body)

    opened = sum(event.startswith("open") for event in peer.events)
    closed = sum(event.startswith("close") for event in peer.events)
    assert opened == closed, f"{opened} opened, {closed} closed: {peer.events}"
