"""The outbound half of reference-v3 (PRD_10 FR1, FR7).

Exactly two tools carry a game on this wire: `receive_turn` for every
half-turn and `submit_audit` to close the sub-game. `receive_commit` and
`receive_reveal` belong to the push dialect, and ali-ahm1's loop never reads
them — a client that calls one is pushing into a void that answers 200.

Every argument arrives under ONE envelope key. The kit's client wraps its
arguments that way, so a tool declaring flat parameters fails Pydantic
validation on the CALLER's side before their code is reached. That is why the
call is asserted as `receive_turn(message=…)` and not by containment.

The nonce is the dangerous field again. It is the only evidence that our
sealed record matches the digest we pushed, it travels once, at the end, and
a nonce sealed but not buffered destroys OUR defence rather than theirs. The
buffer is therefore asserted BY COUNT.
"""

import asyncio

import pytest

from mcp_server import interop
from mcp_server.turn_client import TurnClient


class FakePeer:
    """Records calls the way their server would receive them."""

    def __init__(self):
        self.calls = []

    async def __call__(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return {"status": "accepted"}

    def args_for(self, tool):
        return [kwargs for name, kwargs in self.calls if name == tool]

    def names(self):
        return [name for name, _ in self.calls]


@pytest.fixture
def peer():
    return FakePeer()


@pytest.fixture
def client(peer):
    return TurnClient(peer, sender="police")


def run(coro):
    """The project's async-test idiom: no pytest-asyncio plugin is configured."""
    return asyncio.run(coro)


def test_a_turn_goes_out_under_one_envelope_key(client, peer):
    run(client.turn({"step": 1, "sender": "police"}))

    assert peer.args_for("receive_turn") == [
        {"message": {"step": 1, "sender": "police"}}
    ]


def test_the_push_dialects_tools_are_never_called(client, peer):
    client.seal({"step": 1})
    run(client.turn({"step": 1}))
    run(client.audit({"outcome": "capture"}))

    assert peer.names() == ["receive_turn", "submit_audit"]


def test_sealing_returns_a_wire_shaped_digest(client):
    commit, nonce = client.seal({"step": 1, "move": "MOVE:N"})

    assert commit == interop.commit({"step": 1, "move": "MOVE:N"}, nonce)
    assert len(commit) == 64 and commit == commit.lower()


def test_two_seals_never_share_a_nonce(client):
    """The move set has five elements: a predictable nonce lets an opponent
    brute-force our commitment before the audit discloses it."""
    nonces = {client.seal({"step": step})[1] for step in range(1, 20)}

    assert len(nonces) == 19


def test_every_sealed_step_reaches_the_audit(client, peer):
    for step in range(1, 8):
        client.seal({"step": step})
    run(client.audit({"outcome": "survival"}))

    payload = peer.args_for("submit_audit")[0]["payload"]
    assert len(payload["records"]) == 7
    assert [record["payload"]["step"] for record in payload["records"]] == list(range(1, 8))


def test_the_audit_records_rehash_clean(client, peer):
    client.seal({"step": 1, "move": "MOVE:N"})
    run(client.audit({"outcome": "capture"}))

    record = peer.args_for("submit_audit")[0]["payload"]["records"][0]
    assert interop.commit(record["payload"], record["nonce"]) == record["commit"]


def test_the_audit_declares_our_own_side_and_our_claim(client, peer):
    client.seal({"step": 1})
    run(client.audit({"outcome": "capture", "steps": 1}))

    payload = peer.args_for("submit_audit")[0]["payload"]
    assert payload["sender"] == "police"
    assert payload["result_claim"] == {"outcome": "capture", "steps": 1}


def test_an_empty_audit_is_refused(client):
    """An audit with no records asserts a sub-game we never played, and reads
    to the opponent as a chain with no steps rather than as our own mistake."""
    with pytest.raises(ValueError, match="no records"):
        run(client.audit({"outcome": "capture"}))


def test_the_buffer_is_cleared_so_the_next_sub_game_starts_empty(client, peer):
    client.seal({"step": 1})
    run(client.audit({"outcome": "capture"}))

    with pytest.raises(ValueError):
        run(client.audit({"outcome": "capture"}))
