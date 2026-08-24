"""How connect_and_play treats what the far side raises (10.17).

Split from `test_connect_and_play.py`, which covers the retry policy itself.
This covers the exception TYPES — the half that made a 25-minute window end
on the first refusal, because anyio delivers their 502 wrapped in a
BaseExceptionGroup and `except Exception` silently did not apply.
"""

import asyncio
import contextlib

import pytest

from scripts.reference_launch import connect_and_play


class FlappingPeer:
    """Opens after `failures` refusals, the way a crash-looping peer does."""

    def __init__(self, failures=0, fail_on_push=None, error=None):
        self.failures = failures
        self.opens = 0
        self.pushes = 0
        self.fail_on_push = fail_on_push
        # Defaults to a plain 502. Pass an anyio-style BaseExceptionGroup, or
        # a KeyboardInterrupt, to pin how each is treated.
        self._error = error or RuntimeError("502 Bad Gateway")

    @contextlib.asynccontextmanager
    async def open(self):
        self.opens += 1
        if self.opens <= self.failures:
            raise self._error

        async def call(name, **kwargs):
            if name == "receive_turn":
                self.pushes += 1
                if self.fail_on_push and self.pushes >= self.fail_on_push:
                    raise RuntimeError("peer vanished mid-series")
            return {"accepted": True}

        yield call


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds


def _run(peer, play, seconds=60):
    """`started` is the caller's signal; here it is the peer's own push count.

    connect_and_play no longer infers it by wrapping the call — that could not
    tell a plain call from the per-role factory a two-process opponent needs,
    and guessing wrong pushes a whole sub-game at the wrong peer.
    """
    clock = FakeClock()
    return asyncio.run(connect_and_play(
        peer.open, play, seconds, lambda: peer.pushes > 0,
        interval=1, sleep=clock.sleep, clock=clock))


async def _push_one(call):
    await call("receive_turn", message={"step": 1})
    return "played"


async def _play_nothing(call):
    return "played"


def test_an_anyio_exception_GROUP_still_retries():
    """The reason the retry never fired against a flapping opponent.

    Their 502 reaches us wrapped by anyio's task group, together with the
    CancelledError from tearing that group down — so it arrives as a
    BaseExceptionGroup, which does NOT subclass Exception. `except Exception`
    silently did not apply, and a 25-minute window ended on the first refusal.
    """
    peer = FlappingPeer(failures=3,
                        error=BaseExceptionGroup(
                            "unhandled errors in a TaskGroup",
                            [RuntimeError("502 Bad Gateway")]))

    assert _run(peer, _play_nothing) == "played"
    assert peer.opens == 4


def test_a_real_cancellation_is_never_swallowed():
    """A retry loop that eats KeyboardInterrupt cannot be stopped."""
    peer = FlappingPeer(failures=99, error=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        _run(peer, _play_nothing)

    assert peer.opens == 1, "one attempt, then out"
