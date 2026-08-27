"""A window between sub-games, for an opponent who relaunches (PRD_14).

`play_series` goes from one sub-game's `submit_audit` straight into the next
sub-game's `negotiate`; the gap is milliseconds. That is right for a peer that
serves both roles from one live process, which is what we are.

bb-ai-12 run one manually-launched process per sub-game. Their sub-game-1
process is still inside its shutdown-grace window when our sub-game-2
handshake lands, so it answers declaring its own role and the pairing check
correctly refuses. Five attempts, five identical refusals, and no human-speed
window to hit between an audit and the next handshake.

The ordering test at the bottom is the one that matters: clearing the inbox
AFTER the wait would delete the turns their newly-launched process pushes
during it, which is the deadlock this repo fixed earlier the same day.
"""

import asyncio
from types import SimpleNamespace

import pytest
from claims_series import TERMS, FakeOpponent, StubPolicy, config  # noqa: F401

from scripts.claims_runner import play_series


@pytest.fixture
def apps(config):
    return {role: SimpleNamespace(config=config, inbox=[], audits=[], policy=StubPolicy(),
                                  terms=dict(TERMS),
                                  identity=lambda: {"group_name": "aviayeli"})
            for role in ("police", "thief")}


async def _nothing():
    return None


def _series(apps, sub_games=2, pause_between=None, waits=None, on_wait=None):
    peer = FakeOpponent({role: app.inbox for role, app in apps.items()})
    extra = {}
    if pause_between is not None:
        extra["pause_between"] = pause_between
    if waits is not None:
        async def record(seconds):
            waits.append(seconds)
            if on_wait is not None:
                on_wait()
        extra["pause"] = record
    return asyncio.run(play_series(
        apps, peer, sub_games=sub_games, seed=20260801, wait=_nothing,
        first_role="police", max_steps=1, max_polls=3, **extra))


# --- the wait happens between sub-games, and only there ---------------------


def test_the_wait_happens_once_per_boundary(apps):
    waits = []

    _series(apps, sub_games=4, pause_between=60, waits=waits)

    assert waits == [60, 60, 60], "four sub-games have three boundaries"


def test_there_is_no_wait_before_the_first_sub_game(apps):
    waits = []

    _series(apps, sub_games=1, pause_between=60, waits=waits)

    assert waits == [], "nothing has ended yet; there is nothing to wait for"


def test_the_configured_seconds_are_what_is_waited(apps):
    waits = []

    _series(apps, sub_games=2, pause_between=12.5, waits=waits)

    assert waits == [12.5]


# --- and zero is exactly today (FR2) ---------------------------------------


def test_a_zero_pause_does_not_wait_at_all(apps):
    waits = []

    _series(apps, sub_games=3, pause_between=0, waits=waits)

    assert waits == [], "a zero pause must not sleep, not even for zero"


def test_the_default_is_no_pause(apps):
    """An existing caller must be untouched."""
    waits = []

    _series(apps, sub_games=3, waits=waits)

    assert waits == []


# --- the ordering that keeps this from re-creating the deadlock (FR4) ------


def test_the_inbox_is_cleared_BEFORE_the_wait(apps):
    """Their newly-launched process may negotiate and push its step 1 during
    the window. Clearing after the wait would delete exactly that turn."""
    # We play THIEF in sub-game 2, so their turn comes from the police side.
    theirs = {"step": 1, "sender": "police", "hint": "", "smell_grid": {},
              "commit": "c" * 64, "timestamp": "2026-08-25T00:00:00Z"}
    seen = {}

    def during_wait():
        # What their relaunched peer does while we hold the window open.
        seen["inbox_at_wait"] = list(apps["thief"].inbox)
        apps["thief"].inbox.append(dict(theirs))

    _series(apps, sub_games=2, pause_between=60, waits=[], on_wait=during_wait)

    assert seen["inbox_at_wait"] == [], "the clear had not run before the wait"
    assert any(turn["step"] == 1 for turn in apps["thief"].inbox), (
        "a turn pushed during the window was thrown away"
    )
