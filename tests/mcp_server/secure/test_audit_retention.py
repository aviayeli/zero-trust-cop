"""Their disclosed chain is EVIDENCE — keep it (PRD_10 10.20).

`submit_audit` re-hashed their records, returned a verdict, and dropped the
payload. That payload is the only place their moves and positions are ever
disclosed: `receive_turn` carries a digest and nothing else, so a log written
without it records our chain in full and theirs as sixty-four hex characters
per step.

Which makes two things impossible after the fact:

* verifying THEIR play against the board we both derived — if their contract
  has no `barrier_seed` they walk through cells we hold as walls, and their
  own disclosed positions are what proves it. Nothing on the wire does.
* answering a dispute. We keep the verdict and discard what it was computed
  from, so our artifact asserts a conclusion nobody else can recheck.
"""

import asyncio

from mcp_server import interop


def _record(step, move="MOVE:N"):
    payload = {"step": step, "move": move, "position": [step, 0]}
    nonce = f"{step:032d}"
    return {"payload": payload, "nonce": nonce,
            "commit": interop.commit(payload, nonce)}


def _audit(app, records, sender="thief"):
    return asyncio.run(app.submit_audit({
        "sender": sender, "records": records, "result_claim": {"outcome": "survival"},
    }))


def test_an_accepted_audit_is_retained(app):
    _audit(app, [_record(1), _record(2)])

    assert len(app.audits) == 1
    assert [r["payload"]["step"] for r in app.audits[0]["records"]] == [1, 2]


def test_the_retained_copy_carries_their_positions(app):
    """The whole point: their positions exist nowhere else."""
    _audit(app, [_record(1)])

    assert app.audits[0]["records"][0]["payload"]["position"] == [1, 0]


def test_a_TAMPERED_audit_is_retained_too(app):
    """Especially that one. Discarding the evidence for a verdict of tampering
    leaves us asserting cheating with nothing to show for it."""
    result = _audit(app, [{"payload": {"step": 1}, "nonce": "ab", "commit": "c" * 64}])

    assert result["status"] == "tampered"
    assert len(app.audits) == 1


def test_a_REFUSED_audit_is_not_retained(app):
    """Refusal happens before any state change, as everywhere else on this
    surface — a malformed payload must not enter the record."""
    asyncio.run(app.submit_audit({"sender": "thief", "records": [],
                                  "result_claim": "survival"}))

    assert app.audits == []


def test_the_sender_and_their_claim_are_kept_with_it(app):
    _audit(app, [_record(1)])

    assert app.audits[0]["sender"] == "thief"
    assert app.audits[0]["result_claim"] == {"outcome": "survival"}


def test_our_verdict_is_kept_beside_what_it_was_computed_from(app):
    _audit(app, [_record(1)])

    assert app.audits[0]["verdict"]["status"] == "accepted"
