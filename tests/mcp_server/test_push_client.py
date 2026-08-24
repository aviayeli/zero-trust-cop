"""The outbound half: what we send, and what we must NOT send (PRD_09 FR2-FR3).

Their signatures are narrower than ours, so the client drops fields:
`receive_commit` takes no `signature` and `receive_reveal` takes no `nonce`
and no `state`. Sending an extra keyword would be a TypeError on their side,
so the argument sets are asserted exactly rather than by containment.

The dropped nonce is the dangerous one. It is the only copy of the evidence
that our reveal matched our commitment, and it goes out at sub-game end
through `receive_final_audit`. A nonce dropped and not buffered destroys our
own defence, so the buffer is asserted by COUNT, not by spot check.
"""

import asyncio

import pytest

from mcp_server import interop
from mcp_server.push_client import PushClient


class FakePeer:
    """Records calls the way their server would receive them."""

    def __init__(self):
        self.calls = []

    async def __call__(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return {"status": "accepted"}

    def args_for(self, tool):
        return [kwargs for name, kwargs in self.calls if name == tool]


@pytest.fixture
def peer():
    return FakePeer()


@pytest.fixture
def client(peer):
    return PushClient(peer, role="police")


def run(coro):
    """The project's async-test idiom: no pytest-asyncio plugin is configured."""
    return asyncio.run(coro)


def _seal(client, step, move="MOVE:N", intent="truth", hint="north"):
    """One full half-turn: commit the sealed payload, then reveal it."""
    payload = {"step": step, "move": move, "intent": intent, "hint": hint}
    nonce = f"nonce-{step}"
    run(client.commit(step, interop.commit(payload, nonce), nonce, payload))
    run(client.reveal(step, move=move, hint=hint, intent=intent))


def test_a_commit_carries_no_signature(client, peer):
    run(client.commit(1, "a" * 64, "n1", {"step": 1}))

    assert peer.args_for("receive_commit") == [
        {"role": "police", "step": 1, "h_commit": "a" * 64}
    ]


def test_a_reveal_carries_no_nonce_and_no_state(client, peer):
    run(client.reveal(1, move="MOVE:N", hint="north", intent="truth"))

    sent = peer.args_for("receive_reveal")[0]

    assert sent == {"role": "police", "step": 1, "move": "MOVE:N",
                    "hint": "north", "intent": "truth"}
    assert "nonce" not in sent and "state" not in sent


def test_every_dropped_nonce_is_buffered(client):
    for step in range(1, 8):
        _seal(client, step)

    assert len(client.buffered) == 7


def test_all_buffered_nonces_reach_the_final_audit(client, peer):
    for step in range(1, 8):
        _seal(client, step)

    run(client.final_audit())

    sent = peer.args_for("receive_final_audit")[0]
    assert sent["role"] == "police"
    assert len(sent["nonces"]) == 7
    assert [e["step"] for e in sent["nonces"]] == list(range(1, 8))


def test_each_audit_entry_carries_the_payload_it_sealed(client, peer):
    """We send what we are asking them for: a bare nonce leaves the opponent
    no preimage to rebuild, which is the gap recorded in TODO 9.5."""
    _seal(client, 1)
    run(client.final_audit())

    entry = peer.args_for("receive_final_audit")[0]["nonces"][0]

    assert set(entry) == {"step", "nonce", "payload"}
    assert interop.commit(entry["payload"], entry["nonce"]) == \
        peer.args_for("receive_commit")[0]["h_commit"]


def test_the_buffer_is_cleared_between_sub_games(client):
    _seal(client, 1)
    run(client.final_audit())

    assert client.buffered == []


def test_an_audit_with_nothing_buffered_is_refused(client):
    """Sending an empty audit would assert a sub-game we never played."""
    with pytest.raises(ValueError, match="no nonces"):
        run(client.final_audit())


def test_ack_and_capture_claim_carry_their_exact_fields(client, peer):
    run(client.ack(3))
    run(client.capture_claim(True))

    assert peer.args_for("receive_ack") == [{"role": "police", "step": 3}]
    assert peer.args_for("receive_capture_claim") == [
        {"role": "police", "claimed": True}
    ]
