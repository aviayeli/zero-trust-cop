"""A dead session must be reopened, not reused (PRD_10 10.30).

`lazy_opponents` cached one session per URL and reused it for the whole
series. Against a single-endpoint opponent that means sub-game 2 rides the
connection sub-game 1 opened — and both opponents we played tonight restart
their process between sub-games, so that connection is dead by the time we
need it. Every run ended the same way: sub-game 1 perfect, sub-game 2 dead on
arrival with a 502 we never even tried to recover from.

Reopening is safe HERE and not in `connect_and_play`: the previous sub-game
is already banked and the new one has pushed no turn, so nothing is replayed.

The peer doubles live in `tests/_support/session_revive_peers.py` because
`test_session_revive_close` drives the same restarting endpoint.
"""

import contextlib

import pytest
from session_revive_peers import Restarting, _run


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
