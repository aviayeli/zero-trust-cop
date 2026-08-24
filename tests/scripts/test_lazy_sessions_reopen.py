"""Reopening a flapping endpoint at a sub-game boundary (10.27).

Split from `test_lazy_sessions.py`, which covers WHEN an endpoint is opened.
This covers what happens when that open fails: their cop answered 502 to an
open and 200 to a probe thirty seconds later, so a retry here is the
difference between one sub-game and six. Retrying an OPEN replays nothing —
the previous sub-game is banked and the new one has pushed no turn.
"""

import asyncio
import contextlib

import pytest

from scripts.reference_dial import lazy_opponents


class Dialler:
    def __init__(self, fails=()):
        self.opened = []
        self.fails = set(fails)

    @contextlib.asynccontextmanager
    async def open(self, url, config):
        if url in self.fails:
            raise RuntimeError(f"502 for {url}")
        self.opened.append(url)
        yield lambda tool, **kw: url


ENDPOINTS = {"cop": "https://cop/mcp", "thief": "https://thief/mcp"}


def _reach(dialler, endpoints=None):
    async def go(fn):
        async with lazy_opponents(endpoints or ENDPOINTS, None,
                                  dial=dialler.open) as reach:
            return await fn(reach)
    return go


def test_a_flapping_endpoint_is_retried_at_the_boundary():
    """Their cop returned 502 to our open and 200 to a probe thirty seconds
    later. Opening lazily removed our stale-session cause; this removes the
    other half. Retrying an OPEN replays nothing — the previous sub-game is
    already banked and the new one has pushed no turn yet."""
    class Flaky(Dialler):
        def __init__(self, fail_times):
            super().__init__()
            self.attempts = 0
            self.fail_times = fail_times

        @contextlib.asynccontextmanager
        async def open(self, url, config):
            self.attempts += 1
            if self.attempts <= self.fail_times:
                raise RuntimeError("502 Bad Gateway")
            self.opened.append(url)
            yield lambda tool, **kw: url

    d = Flaky(fail_times=3)

    async def body(reach):
        return await reach("thief")

    async def go():
        async with lazy_opponents(ENDPOINTS, None, dial=d.open,
                                  sleep=_no_wait) as reach:
            return await body(reach)

    asyncio.run(go())

    assert d.attempts == 4
    assert d.opened == ["https://cop/mcp"]


async def _no_wait(_seconds):
    """No real waiting in the suite."""


def test_an_endpoint_that_never_comes_back_still_raises():
    """A retry that never gives up hides a dead opponent forever."""
    class Dead(Dialler):
        @contextlib.asynccontextmanager
        async def open(self, url, config):
            raise RuntimeError("502 Bad Gateway")
            yield  # pragma: no cover

    d = Dead()

    async def go():
        async with lazy_opponents(ENDPOINTS, None, dial=d.open,
                                  sleep=_no_wait) as reach:
            return await reach("thief")

    with pytest.raises(RuntimeError, match="502"):
        asyncio.run(go())
