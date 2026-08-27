"""The audit is checked against what they PUSHED, not only against itself (FR8).

Re-hashing a record against its own `commit` proves the record is internally
consistent. It proves nothing about whether that is the digest the opponent
actually sealed at the time: a peer that rewrites its whole chain after the
sub-game — payload, nonce and commit together — passes a self-consistency
check perfectly.

The evidence that closes it is already in our hands. Every `receive_turn` we
accepted carried that step's `commit`, and it arrived BEFORE the outcome was
known. Comparing the disclosed record against the pushed digest is what turns
the audit from a checksum into a commitment.

Step 0 is exempt on purpose: the fixture is explicit that the sealed step-0
host-spec record is disclosed inside `submit_audit` and never transmitted as
a turn, so there is no pushed digest to compare it against.
"""

import asyncio

from mcp_server import interop


def _turn(step, commit_hex, sender="thief"):
    return {
        "step": step, "sender": sender, "hint": "", "smell_grid": {},
        "commit": commit_hex, "timestamp": "2026-08-24T00:00:00Z",
    }


def _record(step, move="MOVE:N", nonce="112233445566778899aabbccddeeff00"):
    payload = {"step": step, "move": move}
    return {"payload": payload, "nonce": nonce,
            "commit": interop.commit(payload, nonce)}


def _audit(app, records, sender="thief"):
    return asyncio.run(app.submit_audit({
        "sender": sender, "records": records, "result_claim": "survival",
    }))


def test_a_record_matching_the_pushed_digest_is_accepted(app):
    record = _record(1)
    asyncio.run(app.receive_turn(_turn(1, record["commit"])))

    result = _audit(app, [record])

    assert result["status"] == "accepted"
    assert result["records_verified"] == 1


def test_a_chain_rewritten_after_the_fact_is_caught(app):
    """Self-consistent, and NOT what they pushed. This is the whole point."""
    pushed = _record(1, move="MOVE:N")
    rewritten = _record(1, move="MOVE:S")
    asyncio.run(app.receive_turn(_turn(1, pushed["commit"])))

    result = _audit(app, [rewritten])

    assert result["status"] == "tampered"
    assert result["mismatches"] == [1]
    assert result["records_verified"] == 0


def test_the_reason_names_the_digest_they_actually_pushed(app):
    pushed = _record(1, move="MOVE:N")
    asyncio.run(app.receive_turn(_turn(1, pushed["commit"])))

    result = _audit(app, [_record(1, move="MOVE:S")])

    assert pushed["commit"] in result["reason"]


def test_a_step_we_never_received_is_not_faulted_by_the_cross_check(app):
    """Step 0's sealed record is disclosed in the audit and never pushed as a
    turn, so it has no pushed digest to be compared against."""
    result = _audit(app, [_record(0)])

    assert result["status"] == "accepted"


def test_only_the_rewritten_step_is_named(app):
    honest, pushed_two = _record(1), _record(2, move="MOVE:N")
    asyncio.run(app.receive_turn(_turn(1, honest["commit"])))
    asyncio.run(app.receive_turn(_turn(2, pushed_two["commit"])))

    result = _audit(app, [honest, _record(2, move="MOVE:W")])

    assert result["mismatches"] == [2]
    assert result["records_verified"] == 1
