"""Role alternation across a series (PRD_09 FR6).

Split from `test_push_runner.py` at the 150-line limit. The sides swap every
sub-game, so their pushes land in one of our peers in one sub-game and the
other in the next — a runner that served only its starting role would stall
the moment the schedule turned over, which is why both peers are served.
"""

import asyncio

import pytest

from mcp_server import interop
from mcp_server.push_client import PushClient
from mcp_server.server import create_app
from scripts.push_runner import play_series


class FakeOpponent:
    """Records our outbound pushes and answers like a conformant peer."""

    def __init__(self):
        self.calls = []

    async def __call__(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return {"status": "accepted"}

    def names(self):
        return [n for n, _ in self.calls]

    def args_for(self, tool):
        return [k for n, k in self.calls if n == tool]


@pytest.fixture
def thief_app():
    return create_app("thief", dialect="push")


@pytest.fixture
def app():
    """The shipped peer, so the runner is exercised against the real policy
    and the real contract rather than a stub of either."""
    return create_app("police", dialect="push")


def _opponent_feeder(*apps, moves=("MOVE:S",)):
    """Their pushes arriving between our polls, one step per poll.

    Fills every peer we serve, because which of ours they push to changes
    with the role schedule and the opponent does not announce the switch.
    """
    async def wait():
        for app in apps:
            step = len(app.push.commits) + 1
            move = moves[(step - 1) % len(moves)]
            payload = {"step": step, "move": move}
            app.push.commits[step] = interop.commit(payload, f"theirs-{step}")
            app.push.reveals[step] = {"role": "thief", "move": move,
                                      "hint": "", "intent": "truth"}
    return wait


def _play(app, sub_games=1, max_steps=3, moves=("MOVE:S",), apps=None):
    peer = FakeOpponent()
    served = apps or {"police": app}
    summaries = asyncio.run(play_series(
        served, peer, sub_games=sub_games, seed=7,
        wait=_opponent_feeder(*served.values(), moves=moves),
        max_steps=max_steps, first_role="police",
    ))
    return peer, summaries


# --- role alternation ------------------------------------------------------


def test_the_roles_alternate_across_the_series(app, thief_app):
    """A league series swaps sides every sub-game. Playing six as one role
    would contradict the schedule both teams agreed."""
    peer, summaries = _play(app, sub_games=4, max_steps=1,
                            apps={"police": app, "thief": thief_app})

    assert [s["role"] for s in summaries] == ["police", "thief", "police", "thief"]


def test_each_sub_game_declares_the_side_it_played(app, thief_app):
    peer, _ = _play(app, sub_games=2, max_steps=1,
                    apps={"police": app, "thief": thief_app})

    senders = [k["payload"]["sender"] for k in peer.args_for("submit_audit")]

    assert senders == ["police", "thief"]


def test_starting_as_thief_inverts_the_whole_schedule(app, thief_app):
    peer = FakeOpponent()
    summaries = asyncio.run(play_series(
        {"police": app, "thief": thief_app}, peer, sub_games=3, seed=7,
        wait=_opponent_feeder(app, thief_app), max_steps=1, first_role="thief",
    ))

    assert [s["role"] for s in summaries] == ["thief", "police", "thief"]


def test_a_missing_peer_for_a_scheduled_role_is_refused(app):
    """Better than silently playing the wrong side for half the series."""
    with pytest.raises(ValueError, match="thief"):
        asyncio.run(play_series(
            {"police": app}, FakeOpponent(), sub_games=2, seed=7,
            wait=_opponent_feeder(app), max_steps=1, first_role="police",
        ))
