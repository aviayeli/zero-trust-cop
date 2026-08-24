"""Surviving a FLAPPING opponent, without replaying a started series (10.17).

ali-ahm1's server came up and fell over inside the same ten seconds on
2026-08-24: our liveness probe got 200 and the session we opened two seconds
later got 502. Probing first is not enough when the far side flaps — the gap
between "they answer" and "we are connected" is where it dies.

So the connect is retried too. The line that matters is WHERE the retry
stops: the moment a single turn has been pushed, this series is underway and
a retry would replay it — a second sub-game 1 against an opponent already
holding the first, with two sealed chains for one game. Failing loudly beats
that, every time.
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


def test_a_peer_that_is_up_is_connected_once():
    peer = FlappingPeer(failures=0)

    assert _run(peer, _play_nothing) == "played"
    assert peer.opens == 1


def test_a_flapping_peer_is_reconnected_until_it_holds():
    peer = FlappingPeer(failures=4)

    assert _run(peer, _play_nothing) == "played"
    assert peer.opens == 5


def test_a_series_that_has_pushed_a_turn_is_never_replayed():
    """The whole point. A retry here would hand them a second sub-game 1
    while they still hold the first — two sealed chains for one game."""
    peer = FlappingPeer(failures=0, fail_on_push=1)

    with pytest.raises(RuntimeError, match="peer vanished mid-series"):
        _run(peer, _push_one)

    assert peer.opens == 1


def test_giving_up_raises_THEIR_error_not_a_generic_timeout():
    peer = FlappingPeer(failures=999)

    with pytest.raises(RuntimeError, match="502 Bad Gateway"):
        _run(peer, _play_nothing, seconds=3)


def test_the_window_bounds_the_reconnects():
    peer = FlappingPeer(failures=999)

    with pytest.raises(RuntimeError):
        _run(peer, _play_nothing, seconds=4)

    assert peer.opens == 5


def test_one_window_means_one_window():
    """`--wait-minutes 30` held for up to SIXTY: a liveness probe retried for
    the full window and then `connect_and_play` retried for another. The probe
    was added when the connect could not retry, and left in when it could.

    One mechanism now. A peer that is down fails `open_session`, which is the
    same signal the probe was reading, so the probe bought nothing but a
    second deadline nobody could see.
    """
    peer = FlappingPeer(failures=999)
    clock = FakeClock()

    with pytest.raises(RuntimeError):
        asyncio.run(connect_and_play(peer.open, _play_nothing, 10,
                                     lambda: peer.pushes > 0,
                                     interval=1, sleep=clock.sleep, clock=clock))

    assert clock.now == 10, "the window is spent once, not twice"
