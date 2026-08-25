"""The pool of opponent sessions a series holds, and when to drop them.

Split from ``reference_dial`` at the 150-line limit, on a real seam: that
module knows how to open ONE session, this knows which are open, when they
open, and when they must go.

Two live failures shaped it. Opening every endpoint at series start held the
other process's session idle through all of sub-game 1 and it was reaped
before sub-game 2 addressed it -- hence opening on first use. And holding a
session across a sub-game PAUSE died the same way for the opposite reason:
the window exists so the opponent can exit, and their exit killed the session
we were still holding (PRD_15) -- hence ``release``.
"""

from __future__ import annotations

import contextlib

from scripts.reference_dial import opponent

# Pause between attempts on a flapping endpoint.
_REOPEN_WAIT_SEC = 5.0


@contextlib.asynccontextmanager
async def lazy_opponents(endpoints: dict, config, dial=None,
                         attempts: int = 36, sleep=None):
    """Yield ``async (our_role) -> call``, opening each endpoint ON FIRST USE.

    Opening everything at series start held the OTHER process's session idle
    through all of sub-game 1 -- 190+ seconds against a 180s watchdog -- so it
    was reaped before sub-game 2 addressed it. Nine attempts died at the
    boundary and the boundary was never the cause.

    A session opens once per endpoint and is then reused, so every push inside
    a sub-game rides one connection, and a down endpoint costs nothing until
    the schedule reaches it. ``release`` drops them at a boundary (PRD_15).

    A failing open is retried: their cop returned 502 to our open and 200 to a
    probe thirty seconds later. Retrying replays nothing -- the previous
    sub-game is banked and the new one has pushed no turn -- which is why it
    is safe here and not in ``connect_and_play``, where a reconnect would hand
    them a second copy of a series already under way.
    """
    import asyncio as _asyncio

    waiter = sleep or _asyncio.sleep
    from scripts.opponent_endpoints import endpoint_for

    opener = dial or opponent
    calls: dict = {}
    # One stack PER URL: a shared one unwinds LIFO with no notion of "close
    # that one", so no session could be dropped at a boundary.
    stacks: dict = {}

    async def release():
        """Close and FORGET every open endpoint (PRD_15).

        Called at a boundary, before a pause. The far side is EXPECTED to be
        gone, so a raising close is normal and suppressed per URL; one we
        could not close politely is still one we must never reuse.
        """
        for url, sub in list(stacks.items()):
            with contextlib.suppress(BaseException):
                await sub.aclose()
            stacks.pop(url, None)
            calls.pop(url, None)

    async with contextlib.AsyncExitStack() as stack:
        stack.push_async_callback(release)

        async def _open(url):
            """Open one endpoint, retrying while it is flapping."""
            for attempt in range(attempts):
                sub = contextlib.AsyncExitStack()
                try:
                    call = await sub.enter_async_context(opener(url, config))
                    stacks[url] = sub
                    return call
                except BaseException as failure:
                    # BaseException: anyio wraps their 502 in a task group,
                    # so it arrives as a BaseExceptionGroup.
                    if isinstance(failure, (KeyboardInterrupt, SystemExit)):
                        raise
                    if attempt == attempts - 1:
                        raise
                    await waiter(_REOPEN_WAIT_SEC)

        def _reviving(url):
            """A call that REPLACES its session when the far side has gone.

            One session per URL was cached and reused for the whole series.
            Against a single-endpoint opponent that means sub-game 2 rides
            the connection sub-game 1 opened -- and both groups we played
            restart their process between sub-games, so it is dead before we
            touch it. Every run ended the same way: sub-game 1 perfect,
            sub-game 2 dead on arrival.

            Safe here and not in ``connect_and_play``: the previous sub-game
            is banked and the new one has pushed no turn, so a reopen replays
            nothing.
            """
            async def call(tool, **kwargs):
                try:
                    return await calls[url](tool, **kwargs)
                except BaseException as failure:
                    if isinstance(failure, (KeyboardInterrupt, SystemExit)):
                        raise
                    calls[url] = await _open(url)
                    return await calls[url](tool, **kwargs)

            return call

        async def reach(role):
            url = endpoint_for(endpoints, role)
            if url not in calls:
                calls[url] = await _open(url)
            return _reviving(url)

        reach.release = release
        yield reach
