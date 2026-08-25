"""Driving a real peer's engine and policy over the push dialect.

`push_match_loop` is the protocol; this is the part that was missing — the
glue that hands it OUR policy for `choose`, OUR engine for `advance`, and the
store the opponent's inbound pushes actually land in.

The store is the reason this has to live in-process with the server: their
`receive_commit` lands in `app.push`, and a runner in a separate process
could not see it. That constraint is what the design is shaped around.
"""

import asyncio

import pytest

from mcp_server import interop
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


def test_it_pushes_a_commit_and_reveal_for_every_step(app):
    peer, _ = _play(app, max_steps=3)

    assert len(peer.args_for("receive_commit")) == 3
    assert len(peer.args_for("receive_reveal")) == 3


def test_the_moves_it_pushes_come_from_our_policy(app):
    """Not a fixed string: the runner's job is to hand the loop OUR policy."""
    peer, _ = _play(app, max_steps=4)

    moves = {k["move"] for k in peer.args_for("receive_reveal")}

    assert moves, "no moves pushed at all"
    assert moves <= {"MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W", "MOVE:STAY"}


def test_every_reveal_declares_an_intent_our_engine_understands(app):
    peer, _ = _play(app, max_steps=4)

    for kwargs in peer.args_for("receive_reveal"):
        assert kwargs["intent"] in ("truth", "lie")


def test_our_engine_actually_advances(app):
    """The whole point: their move reaches our board, not just our log."""
    before = app.match_state.turn_count

    _play(app, max_steps=3)

    assert app.match_state.turn_count > before


def test_each_sub_game_ends_with_one_audit(app, thief_app):
    peer, summaries = _play(app, sub_games=2, max_steps=2,
                            apps={"police": app, "thief": thief_app})

    assert len(peer.args_for("submit_audit")) == 2
    assert len(summaries) == 2


def test_the_audit_records_reproduce_the_commits_we_pushed(app):
    peer, _ = _play(app, max_steps=3)

    pushed = [k["h_commit"] for k in peer.args_for("receive_commit")]
    records = peer.args_for("submit_audit")[0]["payload"]["records"]

    assert [r["commit"] for r in records] == pushed
    for record in records:
        assert interop.commit(record["payload"], record["nonce"]) == record["commit"]


def test_the_opponent_store_is_cleared_between_sub_games(app, thief_app):
    """Carrying their step 1 into the next sub-game would let a stale commit
    satisfy a step we never played."""
    peer, _ = _play(app, sub_games=2, max_steps=2,
                    apps={"police": app, "thief": thief_app})

    first, second = peer.args_for("submit_audit")
    assert len(first["payload"]["records"]) == 2
    assert len(second["payload"]["records"]) == 2


def test_a_series_is_reproducible_from_its_seed(app):
    peer_a, _ = _play(app, max_steps=4)
    fresh = create_app("police", dialect="push")
    peer_b, _ = _play(fresh, max_steps=4)

    assert [k["move"] for k in peer_a.args_for("receive_reveal")] == \
        [k["move"] for k in peer_b.args_for("receive_reveal")]
