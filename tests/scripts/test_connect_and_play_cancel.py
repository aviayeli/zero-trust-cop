"""The retry must survive the dead session's own cancellation (PRD_11).

Split from `test_connect_and_play_errors.py` at the 150-line limit; the seam
is real. That module pins which exception TYPES are retried. This pins the
cancellation that arrives *alongside* them, which is a different mechanism and
cost a live window on 2026-08-25.

What happened: `--wait-minutes 45` gave up after 183 seconds against bb-ai-12
— one `lazy_opponents` budget (36 x 5s), no outer retry at all, and nothing on
stdout said the window had collapsed. `streamable_http_client` hosts its
session in an anyio task group; when the session fails, anyio cancels the
scope, and on asyncio that lands as a cancellation pending on OUR task. The
retry's own `await sleep(...)` was the next await point, so it re-raised and
unwound the whole run.

Every other test of this function injects a fake sleep that cannot raise,
which is precisely why the defect went unseen for the phase that introduced
it. These use the real one.
"""

import asyncio
import contextlib

import pytest

from scripts.reference_launch import connect_and_play


class Peer:
    """Refuses `failures` times, then opens. Optionally cancelling as it dies."""

    def __init__(self, failures=0, cancel_on_fail=False):
        self.failures = failures
        self.cancel_on_fail = cancel_on_fail
        self.opens = 0
        self.pushes = 0

    @contextlib.asynccontextmanager
    async def open(self):
        self.opens += 1
        if self.opens <= self.failures:
            if self.cancel_on_fail:
                # Exactly what the dying task group does to its host task.
                asyncio.current_task().cancel()
            raise RuntimeError("502 Bad Gateway")

        async def call(name, **kwargs):
            return {"accepted": True}

        yield call


async def _play_nothing(call):
    return "played"


def _run(peer, seconds=60, interval=0, sleep=None):
    kwargs = {"interval": interval}
    if sleep is not None:
        kwargs["sleep"] = sleep
    return asyncio.run(connect_and_play(
        peer.open, _play_nothing, seconds, lambda: peer.pushes > 0, **kwargs))


def test_a_teardown_cancellation_does_not_end_the_window():
    """The live defect: one attempt instead of a 45-minute window."""
    peer = Peer(failures=3, cancel_on_fail=True)

    assert _run(peer) == "played"
    assert peer.opens == 4, "each teardown cancellation must cost one retry"


def test_the_window_still_bounds_a_cancelling_peer():
    """Absorbing the cancellation must not make the retry loop unbounded."""
    peer = Peer(failures=999, cancel_on_fail=True)

    with pytest.raises(RuntimeError, match="502 Bad Gateway"):
        _run(peer, seconds=0)

    assert peer.opens == 1


def test_a_cancellation_nobody_requested_is_still_fatal():
    """Only the dead session's OWN cancellation is absorbed. One with no
    request behind it belongs to a shutdown we must not swallow."""
    async def cancelled_sleep(seconds):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        _run(Peer(failures=99), interval=1, sleep=cancelled_sleep)


def test_a_real_interrupt_still_stops_the_loop():
    """Belt and braces: the absorbing branch must not catch KeyboardInterrupt."""
    class Interrupting(Peer):
        @contextlib.asynccontextmanager
        async def open(self):
            self.opens += 1
            raise KeyboardInterrupt
            yield  # unreachable; makes this a generator, not a coroutine

    peer = Interrupting()
    with pytest.raises(KeyboardInterrupt):
        _run(peer)

    assert peer.opens == 1
