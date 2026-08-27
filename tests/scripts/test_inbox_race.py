"""A turn that arrives during our handshake must survive it.

Found live against bb-ai-12 on 2026-08-25, and found by THEM: their inbound
log showed our server answering `{"status":"accepted","step":1}` to their
step 1, while our own stall diagnostic showed an inbox holding only step 2.
Both were true.

`claims_runner` opens each sub-game with

    handshake = await negotiate(...)   # a network round-trip
    app.inbox.clear()                  # unconditional

Our server is bound and answering throughout. An opponent that negotiates and
pushes immediately lands its step 1 in our inbox *during* that round-trip, and
the clear then destroys it. We wait for a step 1 we already had and threw away;
they wait for our step 2, which we will not send until we see their step 1.
Neither side errors, and both re-push forever.

The clear itself is right -- a turn from the previous sub-game would otherwise
satisfy this one's step 1. What was wrong is doing it AFTER an awaited call
that the opponent can push into.
"""

import asyncio
from types import SimpleNamespace

import pytest
from claims_series import TERMS, StubPolicy, config  # noqa: F401

from mcp_server import interop
from scripts.claims_runner import play_series


def _their_turn(step: int, sender: str = "thief", commit: str = "c") -> dict:
    return {"step": step, "sender": sender, "hint": "", "commit": commit * 64,
            "smell_grid": {"3,3": 0.9}, "timestamp": "2026-08-25T11:17:54Z"}


class PushesDuringHandshake:
    """Negotiates, then pushes step 1 at once -- and answers nothing after.

    That is bb-ai-12's real shape: their peer opens, pushes, and waits. The
    only way the sub-game can proceed is if the turn they pushed while our
    handshake was in flight is still in our inbox when the loop starts.
    """

    def __init__(self, inbox):
        self.inbox = inbox
        self.pushed_during_handshake = 0

    async def __call__(self, tool, **kwargs):
        if tool == "negotiate":
            self.inbox.append(_their_turn(1))
            self.pushed_during_handshake += 1
            nonce = "theirs"
            return {"status": "accepted", "terms": dict(TERMS), "nonce": nonce,
                    "signature": interop.terms_signature(TERMS, nonce),
                    "role": "thief"}
        return {"status": "accepted"}


@pytest.fixture
def apps(config):
    return {role: SimpleNamespace(config=config, inbox=[], audits=[], policy=StubPolicy(),
                                  terms=dict(TERMS),
                                  identity=lambda: {"group_name": "aviayeli"})
            for role in ("police", "thief")}


async def _nothing():
    return None


def test_a_turn_pushed_during_the_handshake_is_not_thrown_away(apps):
    """The live deadlock, reduced. Their step 1 arrives while our negotiate
    round-trip is in flight; the sub-game must still see it."""
    peer = PushesDuringHandshake(apps["police"].inbox)

    summaries = asyncio.run(play_series(
        apps, peer, sub_games=1, seed=20260801, wait=_nothing,
        first_role="police", max_steps=1, max_polls=3,
    ))

    assert peer.pushed_during_handshake == 1
    assert summaries[0]["steps"] == 1, (
        "the sub-game stalled on a step 1 we had already received"
    )


def test_the_previous_sub_games_residue_is_still_dropped(apps):
    """The clear exists for a reason and must keep doing its job: a turn left
    over from the last sub-game must not satisfy this one's step 1."""
    # A DIFFERENT commit, so it cannot be confused with the fresh step 1 the
    # opponent pushes during the handshake -- these are compared by value.
    stale = _their_turn(1, commit="d")
    apps["police"].inbox.append(stale)
    peer = PushesDuringHandshake(apps["police"].inbox)

    asyncio.run(play_series(
        apps, peer, sub_games=1, seed=20260801, wait=_nothing,
        first_role="police", max_steps=1, max_polls=3,
    ))

    assert stale not in apps["police"].inbox, "stale turn survived the boundary"
