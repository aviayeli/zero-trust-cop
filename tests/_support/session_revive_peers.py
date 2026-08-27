"""Doubles for the session-revive tests (PRD_10 10.30).

Two test modules drive `lazy_opponents` against a peer that dies mid-series:
`test_session_revive` covers reuse, revival and a peer that stays down, and
`test_session_revive_close` covers the ORDER of opens and closes that the
sub-game-1 boundary crash turned on. Both need the same restarting endpoint,
and a double copied into two files is a double that drifts between them.

Lives under `tests/_support` because `pythonpath` names that directory; a
`tests/scripts` package would collide with the `scripts` package in `src`.
"""

import asyncio
import contextlib

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
