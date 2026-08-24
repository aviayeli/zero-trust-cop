"""The outbound half: what we send, and what we must NOT send (PRD_09 FR2-FR3).

Their signatures are narrower than ours, so the client drops fields:
`receive_commit` takes no `signature` and `receive_reveal` takes no `nonce`
and no `state`. Sending an extra keyword would be a TypeError on their side,
so the argument sets are asserted exactly rather than by containment.

The dropped nonce is the dangerous one. It is the only copy of the evidence
that our reveal matched our commitment, and it goes out at sub-game end
through `submit_audit`. A nonce dropped and not buffered destroys our own
defence, so the buffer is asserted by COUNT, not by spot check.

The audit step is `submit_audit(payload={sender, records, result_claim})`,
each record `{payload, nonce, commit}` — confirmed by ali-ahm1 on 2026-08-24,
correcting their earlier `receive_final_audit(role, nonces)`. The correction
matters: the flat form carried bare nonces with no preimage to rebuild, so
the audit was not merely late, it was uncomputable. This shape closes it.
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

    def names(self):
        return [name for name, _ in self.calls]


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


def test_all_buffered_nonces_reach_the_audit(client, peer):
    for step in range(1, 8):
        _seal(client, step)

    run(client.final_audit({"outcome": "capture"}))

    sent = peer.args_for("submit_audit")[0]["payload"]
    assert sorted(sent) == ["records", "result_claim", "sender"]
    assert sent["sender"] == "police"
    assert sent["result_claim"] == {"outcome": "capture"}
    assert len(sent["records"]) == 7


def test_the_audit_goes_to_submit_audit_not_the_flat_form(client, peer):
    """ali-ahm1 corrected this on 2026-08-24: reference-v3 uses submit_audit,
    and they never call receive_final_audit in a series."""
    _seal(client, 1)
    run(client.final_audit({"outcome": "capture"}))

    assert peer.names() == ["receive_commit", "receive_reveal", "submit_audit"]
    assert "receive_final_audit" not in peer.names()


def test_each_record_carries_the_full_preimage(client, peer):
    """{payload, nonce, commit} — everything needed to recompute the digest,
    so neither side has to reconstruct the other's payload."""
    _seal(client, 1)
    run(client.final_audit({"outcome": "capture"}))

    record = peer.args_for("submit_audit")[0]["payload"]["records"][0]

    assert sorted(record) == ["commit", "nonce", "payload"]
    assert interop.commit(record["payload"], record["nonce"]) == record["commit"]
    assert record["commit"] == peer.args_for("receive_commit")[0]["h_commit"]


def test_the_buffer_is_cleared_between_sub_games(client):
    _seal(client, 1)
    run(client.final_audit({"outcome": "capture"}))

    assert client.buffered == []


def test_an_audit_with_nothing_buffered_is_refused(client):
    """Sending an empty audit would assert a sub-game we never played."""
    with pytest.raises(ValueError, match="no records"):
        run(client.final_audit({"outcome": "capture"}))


def test_ack_and_capture_claim_carry_their_exact_fields(client, peer):
    run(client.ack(3))
    run(client.capture_claim(True))

    assert peer.args_for("receive_ack") == [{"role": "police", "step": 3}]
    assert peer.args_for("receive_capture_claim") == [
        {"role": "police", "claimed": True}
    ]
