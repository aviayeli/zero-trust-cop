"""Re-push while waiting, so their start time stops mattering (10.25).

We pushed each step ONCE and then polled. If the opponent's loop was not
reading yet — because their process starts, plays, finishes and exits on its
own schedule — our step 1 landed in a queue nobody drained and both sides
waited out their budgets. Against rstabcde that cost three attempts in forty
minutes, each needing the two launches synchronised to the second.

Re-pushing the SAME sealed turn costs nothing: identical bytes, identical
digest, and the receiver is required to tolerate a repeat (the kit's
at-least-once delivery contract). It converts a coordination problem into a
retry.
"""

import asyncio

import pytest

from scripts.claims_guards import await_turn


class Inbox(list):
    """Their turn lands after a set number of polls."""

    def __init__(self, arrives_after):
        super().__init__()
        self.polls = 0
        self._after = arrives_after

    async def wait(self):
        self.polls += 1
        if self.polls >= self._after:
            self.append({"step": 1, "sender": "thief"})


def _run(inbox, repush=None, every=3):
    return asyncio.run(await_turn(inbox, 1, inbox.wait, 20, "police",
                                  repush=repush, repush_every=every))


def test_a_turn_that_arrives_needs_no_repush():
    inbox = Inbox(arrives_after=1)
    sent = []

    _run(inbox, repush=lambda: sent.append(1))

    assert sent == []


def test_we_repush_while_they_are_still_silent():
    inbox = Inbox(arrives_after=10)
    sent = []

    async def repush():
        sent.append(1)

    _run(inbox, repush=repush, every=3)

    assert len(sent) >= 2, "silence must trigger more than one retry"


def test_the_loop_still_works_without_a_repush():
    """Diagnostics and resilience, never a dependency."""
    inbox = Inbox(arrives_after=2)

    assert _run(inbox)["step"] == 1


def test_a_repush_that_fails_does_not_kill_the_wait():
    """Their endpoint may be down for exactly the seconds we retry into. A
    failed retry is a reason to keep waiting, not to end the sub-game."""
    inbox = Inbox(arrives_after=8)

    async def repush():
        raise RuntimeError("502 Bad Gateway")

    assert _run(inbox, repush=repush, every=2)["step"] == 1
