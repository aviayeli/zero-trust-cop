"""Drop the opponent's sessions at the sub-game boundary (PRD_15).

PRD_14's pause worked -- the first live run with it crossed the boundary with
zero pairing collisions, where five previous attempts had all collided -- and
died anyway, two seconds before the window closed.

`lazy_opponents` holds a session per endpoint for the whole series, and the
pause sits inside that hold. So we slept for ninety seconds still holding
their session, their sub-game-1 process exited (which is the entire point of
the window), the held session's background stream failed 502, and its anyio
task group unwound through our exit stack and killed the run.

The module's own docstring already records this shape: a session held idle for
190 seconds against a 180-second watchdog was reaped, and lazy opening was the
fix. The pause put the idle hold back, across the one interval in which the
opponent is expected to disappear.
"""

import asyncio
import contextlib

from scripts.reference_dial import lazy_opponents

ENDPOINTS = {"cop": "https://cop/mcp", "thief": "https://thief/mcp"}


class Dialler:
    """Records opens and closes, and can fail a close the way a dead peer does."""

    def __init__(self, close_raises=False):
        self.opened = []
        self.closed = []
        self.close_raises = close_raises

    @contextlib.asynccontextmanager
    async def open(self, url, config):
        self.opened.append(url)
        try:
            yield lambda tool, **kw: url
        finally:
            self.closed.append(url)
            if self.close_raises:
                # What a session whose far side has already gone really does.
                raise BaseExceptionGroup("tg", [RuntimeError("502")])


def _run(dialler, body):
    async def go():
        async with lazy_opponents(ENDPOINTS, None, dial=dialler.open) as reach:
            return await body(reach)

    return asyncio.run(go())


# --- the release itself ----------------------------------------------------


def test_the_reach_callable_carries_a_release():
    """Attached to the callable so every existing caller is untouched."""
    async def body(reach):
        assert callable(getattr(reach, "release", None))

    _run(Dialler(), body)


def test_releasing_closes_the_session_that_was_open():
    d = Dialler()

    async def body(reach):
        await reach("police")
        assert d.closed == []
        await reach.release()
        assert d.closed == ["https://thief/mcp"]

    _run(d, body)


def test_the_next_sub_game_opens_a_FRESH_session():
    """FR2: a released endpoint must look exactly like one never opened."""
    d = Dialler()

    async def body(reach):
        await reach("police")
        await reach.release()
        await reach("police")

    _run(d, body)

    assert d.opened == ["https://thief/mcp", "https://thief/mcp"]


def test_releasing_nothing_is_a_no_op():
    d = Dialler()

    async def body(reach):
        await reach.release()

    _run(d, body)

    assert d.opened == [] and d.closed == []


def test_release_is_idempotent():
    d = Dialler()

    async def body(reach):
        await reach("police")
        await reach.release()
        await reach.release()

    _run(d, body)

    assert d.closed == ["https://thief/mcp"]


# --- and it cannot fail the series (FR3) -----------------------------------


def test_a_close_that_raises_does_not_end_the_series():
    """The far side being gone is the NORMAL case here -- it is what the
    window exists for -- so a raising close must not propagate."""
    d = Dialler(close_raises=True)

    async def body(reach):
        await reach("police")
        await reach.release()
        return "survived"

    assert _run(d, body) == "survived"


def test_an_endpoint_that_would_not_close_is_still_forgotten():
    """A session we could not close politely is still one we must never
    reuse."""
    d = Dialler(close_raises=True)

    async def body(reach):
        await reach("police")
        await reach.release()
        await reach("police")

    _run(d, body)

    assert d.opened == ["https://thief/mcp", "https://thief/mcp"]
