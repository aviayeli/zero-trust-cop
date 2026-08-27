"""The abandoned session must be closed BEFORE its replacement opens.

Split out of `test_session_revive` (which covers reuse and revival) because
the two together crossed the project's 150-line ceiling. These are the two
regression tests for the live failure of 2026-08-26, committed with the fix
in 10a8657; they turn on the ORDER of opens and closes, not on revival.
"""

import contextlib

from session_revive_peers import Restarting, _run


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
