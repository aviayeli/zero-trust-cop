"""The handshake that opens every sub-game (PRD_10 10.13).

Split from `test_claims_runner.py` at the 150-line limit; the seam is the
subject. That module pins the SCHEDULE — who plays which side, what resets
between sub-games. This one pins the gate that has to pass before a single
turn may be pushed.

It exists because nothing ever sent a negotiate. Our server has verified
theirs since the reference-v3 phase and our runner opened a session and
started pushing, which looked sound because our own `receive_turn` does not
gate on a handshake. Theirs does, one layer in: ali-ahm1 confirmed their
server queues turns ungated and their GAME LOOP will not read that queue
until negotiate completes. A turn pushed first is not refused — it is
ignored, which from our side is indistinguishable from a slow peer.
"""

import asyncio

import pytest
from claims_series import (  # noqa: F401  -- `apps`/`config` are FIXTURES
    FakeOpponent,
    _nothing,
    _series,
    apps,
    config,
    play_series,
)


def test_every_sub_game_opens_with_a_handshake(apps):
    """Their loop will not READ the turn queue until negotiate completes, so a
    turn pushed first sits unread and reads to us as a slow peer."""
    peer, _ = _series(apps, sub_games=2, max_steps=2)

    assert [name for name, _ in peer.calls][:2] == ["negotiate", "receive_turn"]
    assert [name for name, _ in peer.calls].count("negotiate") == 2


def test_the_handshake_declares_the_side_we_play_this_sub_game(apps):
    peer, _ = _series(apps, sub_games=3, max_steps=1)

    handshakes = [k["message"] for n, k in peer.calls if n == "negotiate"]
    assert [h["role"] for h in handshakes] == ["police", "thief", "police"]
    assert [h["sub_game_number"] for h in handshakes] == [1, 2, 3]


def test_a_refused_handshake_stops_the_series_before_a_turn_is_pushed(apps):
    class Refusing(FakeOpponent):
        async def __call__(self, tool, **kwargs):
            self.calls.append((tool, kwargs))
            return {"status": "refused", "reason": "terms disagree on max_steps"}

    peer = Refusing({r: a.inbox for r, a in apps.items()})
    with pytest.raises(RuntimeError, match="terms disagree on max_steps"):
        asyncio.run(play_series(apps, peer, sub_games=2, seed=1, wait=_nothing,
                                max_steps=2, max_polls=3))

    assert [name for name, _ in peer.calls] == ["negotiate"]


def test_an_unverified_handshake_is_reported_not_hidden(apps):
    """ali-ahm1 answers a bare `accepted: true`. It opens their queue and
    counter-signs nothing, so the summary must say so — a series played on an
    unchecked handshake is not a series we checked."""
    class Bare(FakeOpponent):
        async def __call__(self, tool, **kwargs):
            if tool == "negotiate":
                self.calls.append((tool, kwargs))
                return {"accepted": True}
            return await super().__call__(tool, **kwargs)

    peer = Bare({r: a.inbox for r, a in apps.items()})
    summaries = asyncio.run(play_series(apps, peer, sub_games=1, seed=1,
                                        wait=_nothing, max_steps=2, max_polls=3))

    assert summaries[0]["handshake_counter_signed"] is False


def test_a_counter_signed_handshake_is_reported_as_such(apps):
    _, summaries = _series(apps, sub_games=1, max_steps=2)

    assert summaries[0]["handshake_counter_signed"] is True
