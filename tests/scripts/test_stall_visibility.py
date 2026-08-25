"""A stalled wait must say so (PRD_12 FR4-FR6).

`await_turn` re-sends the same sealed turn every `repush_every` polls while
their reply is outstanding. That is correct and deliberately cheap. But it
prints nothing, and `claims_match_loop` emits its progress line only AFTER the
wait returns — so a loop stuck on step 1 produces no output at all while
emitting a request every ten seconds.

On 2026-08-25 bb-ai-12 counted nine of our re-pushes of ONE turn as nine turns,
and we counted our own zero progress lines as "we never sent a turn". Both
readings were wrong, and neither side had anything better to go on.

The last test here is the one that matters: a diagnostic that can end a graded
series is worse than no diagnostic.
"""

import asyncio

import pytest

from scripts.claims_guards import await_turn


async def _nothing():
    return None


def _run(inbox, step=1, max_polls=45, repush_every=20, on_repush=None,
         repush=None, ours="police"):
    return asyncio.run(await_turn(
        inbox, step, _nothing, max_polls, ours,
        repush=repush or (lambda: _nothing()),
        repush_every=repush_every, on_repush=on_repush))


# --- the callback fires, once per re-push (FR4) ----------------------------


def test_each_repush_is_reported_with_a_rising_attempt_count():
    seen = []

    with pytest.raises(TimeoutError):
        _run([], on_repush=seen.append)

    assert [entry["attempt"] for entry in seen] == [1, 2]
    assert {entry["step"] for entry in seen} == {1}


def test_an_empty_inbox_is_visible_as_empty():
    """`inbox_depth == 0` is 'they never reached us'."""
    seen = []

    with pytest.raises(TimeoutError):
        _run([], on_repush=seen.append)

    assert seen[0]["inbox_depth"] == 0
    assert seen[0]["inbox_steps"] == []
    assert seen[0]["senders"] == []


def test_a_desync_is_visible_as_a_desync():
    """The distinction that cost a day: they DID reach us, and we are waiting
    on a step number they never send."""
    inbox = [{"step": 0, "sender": "thief"}, {"step": 0, "sender": "thief"}]
    seen = []

    with pytest.raises(TimeoutError):
        _run(inbox, step=1, on_repush=seen.append)

    assert seen[0]["inbox_depth"] == 2
    assert seen[0]["inbox_steps"] == [0, 0]
    assert seen[0]["senders"] == ["thief"]


# --- and it changes nothing (FR5) ------------------------------------------


def test_without_a_callback_the_wait_behaves_exactly_as_before():
    pushes = []

    async def repush():
        pushes.append(1)

    with pytest.raises(TimeoutError):
        _run([], repush=repush)

    assert len(pushes) == 2, "the re-push cadence moved"


def test_their_turn_is_still_returned_the_moment_it_lands():
    theirs = {"step": 1, "sender": "thief"}
    seen = []

    got = _run([theirs], on_repush=seen.append)

    assert got is theirs
    assert seen == [], "nothing was outstanding, so nothing was re-pushed"


# --- and it can never break a live series (FR5) ----------------------------


def test_a_raising_callback_never_ends_the_wait():
    """The one that matters. A diagnostic that can kill a graded run is worse
    than no diagnostic at all."""
    def explode(entry):
        raise RuntimeError("the diagnostic itself is broken")

    theirs = {"step": 1, "sender": "thief"}
    inbox = []

    async def land_it():
        inbox.append(theirs)

    got = _run(inbox, on_repush=explode, repush=land_it)

    assert got is theirs
