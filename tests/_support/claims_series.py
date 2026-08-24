"""Doubles for a reference-v3 SERIES, shared by the runner tests.

Two test modules drive `play_series` — one for the schedule, one for the
handshake that opens every sub-game — and both need the same three things:
a policy stub narrowed to the surface the runner actually touches, an
opponent that answers a negotiate and mirrors every pushed turn back into
the right inbox, and a peer namespace shaped like `create_app`'s.

The stub is narrow ON PURPOSE. `StubPolicy` exposes `state_key`, `decide`,
`intent_for_move` and `pheromones` and nothing else, so a runner that starts
reaching for another member of the real `AgentPolicy` fails here rather than
passing against a mock that answers anything.

Lives under `tests/_support` because `pythonpath` names that directory; a
`tests/scripts` package would collide with the `scripts` package in `src`.
"""

import asyncio
from types import SimpleNamespace

import pytest

from engine.config import load_config
from mcp_server import interop
from scripts.claims_runner import play_series


class StubPolicy:
    """The policy surface the runner actually uses, and nothing else."""

    def __init__(self):
        self.deposits = []
        self.pheromones = SimpleNamespace(advance=self._advance, strongest=lambda: None)

    def _advance(self, deposits=()):
        self.deposits.extend(deposits)

    def state_key(self, own, opponent, board):
        return (opponent, own)

    def decide(self, state, rng):
        return "STAY", "staying put"

    def intent_for_move(self, token):
        return "stay"


class FakeOpponent:
    """Answers every pushed turn with one of its own, into the right inbox."""

    def __init__(self, inboxes, claim=None):
        self.inboxes = inboxes
        self.claim = claim
        self.calls = []

    async def __call__(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        if tool == "negotiate":
            theirs = kwargs["message"]["role"]
            nonce = "theirs"
            return {
                "status": "accepted", "terms": dict(TERMS), "nonce": nonce,
                "signature": interop.terms_signature(TERMS, nonce),
                "role": "thief" if theirs == "police" else "police",
            }
        if tool == "receive_turn":
            ours = kwargs["message"]
            reply = {
                "step": ours["step"],
                "sender": "thief" if ours["sender"] == "police" else "police",
                "hint": "", "smell_grid": {"3,3": 0.9}, "commit": "c" * 64,
                "timestamp": "2026-08-24T00:00:00Z",
            }
            if self.claim is not None and ours["sender"] == "thief":
                reply["capture_claim"] = list(self.claim)
            self.inboxes[ours["sender"]].append(reply)
        return {"status": "accepted"}

    def audits(self):
        return [kwargs["payload"] for name, kwargs in self.calls
                if name == "submit_audit"]


@pytest.fixture
def config():
    return load_config("config/game.json")


TERMS = {"board_size": 7, "max_steps": 35}


@pytest.fixture
def apps(config):
    return {role: SimpleNamespace(config=config, inbox=[], policy=StubPolicy(),
                                  terms=dict(TERMS),
                                  identity=lambda: {"group_name": "aviayeli"})
            for role in ("police", "thief")}


async def _nothing():
    """Their turn is already in the inbox by the time we poll."""


def _series(apps, sub_games=6, max_steps=2, first_role="police", claim=None):
    peer = FakeOpponent({role: app.inbox for role, app in apps.items()}, claim=claim)
    summaries = asyncio.run(play_series(
        apps, peer, sub_games=sub_games, seed=20260801, wait=_nothing,
        first_role=first_role, max_steps=max_steps, max_polls=3,
    ))
    return peer, summaries
