"""Getting connected, and staying patient, when the far side is not (10.16-17).

Three small pieces the live entry point needs and should not carry itself.

``polls_for`` turns an operator's wait window into the loop's poll budget from
the peer's CONFIGURED interval, never a literal: a peer polling every two
seconds must not silently get a quarter of the window it asked for.

``connect_and_play`` exists because of two live failures on 2026-08-24. First
our runner dialled the opponent at startup and died on their 502 -- which took
our OWN servers down with it, since the peers live only for the length of a
run, making "we come up first and signal you" impossible by construction. Then
their server turned out to FLAP: a liveness probe answered 200 and the session
opened two seconds later got 502.

A separate probe was the first fix and is gone: it retried for the whole
window and then the connect retried for another, so ``--wait-minutes 30`` held
for up to sixty and nothing said so. One mechanism now -- a peer that is down
fails ``open_session`` with the same error the probe was reading.

We wait for them, and we reconnect when they drop -- but only until the first
turn is pushed. After that the series is underway and a reconnect would replay
it. The transport itself is in ``reference_dial``.
"""

from __future__ import annotations

import asyncio
import time

_SECONDS_PER_MINUTE = 60


def polls_for(minutes: float, poll_interval_sec: float) -> int:
    """How many polls fill a wait window of ``minutes``.

    Never zero: a window that rounded down to no polls would have the loop
    report a stall it never waited through.
    """
    return max(1, int(minutes * _SECONDS_PER_MINUTE / poll_interval_sec))


async def connect_and_play(open_session, play, seconds: float, started,
                           interval: float = 5.0, sleep=asyncio.sleep,
                           clock=time.monotonic):
    """Open a session and play through it, reconnecting while they flap.

    Probing first is not enough against a peer that crash-loops: ali-ahm1's
    liveness probe answered 200 and the session opened two seconds later got
    502. The gap between "they answer" and "we are connected" is where it
    died, so the connect is retried too.

    The retry STOPS as soon as ``started()`` is true. That is the whole
    design: the series is then underway, and reconnecting would replay it --
    handing them a second sub-game 1 while they still hold the first, two
    sealed chains for one game. Failing loudly beats that every time.

    ``started`` is the CALLER's, not ours: what "underway" means depends on
    how the caller reaches the opponent, and an earlier build that inferred it
    by wrapping the call could not tell a plain call from the per-role factory
    a two-process opponent needs.

    Args:
        open_session: async context manager factory yielding whatever ``play``
            needs -- one call, or a factory over the opponent's endpoints.
        play: async ``(reached) -> result``.
        seconds: how long to keep reconnecting BEFORE the series starts.
        started: ``() -> bool``; True once a turn has been pushed.

    Raises:
        Whatever the far side raised -- their 502, not a generic timeout, so
        the operator can see it was the opponent that never held.
    """
    deadline = clock() + seconds

    while True:
        try:
            async with open_session() as reached:
                return await play(reached)
        except BaseException as failure:
            # BaseException, not Exception. Their 502 reaches us wrapped by
            # anyio's task group together with the CancelledError from
            # tearing it down, so it arrives as a BaseExceptionGroup -- which
            # does NOT subclass Exception. `except Exception` silently did not
            # apply, and a 25-minute window ended on the first refusal.
            if isinstance(failure, (KeyboardInterrupt, SystemExit)):
                raise
            if started() or clock() >= deadline:
                raise failure
            await sleep(interval)
