"""The opponent's disclosed chain, and our verdict on it, must reach disk.

Our server already verifies an inbound audit and appends it to an in-process
`audits` list, and reference_tools' own docstring says why that list exists:
"discarding the payload meant asserting a verdict nobody could recheck".

The list was never written anywhere. It died with the runner process, and an
ACCEPTED audit logged nothing, so after a series we held a verdict nobody
could recheck -- the exact thing that docstring warns against.

It surfaced against SMNGRP05. We told them "zero records disclosed" from
`their_audit_response`, which is the REPLY to our own outbound call -- their
receipt for our payload, never a carrier for theirs. When they asked whether
we had logged an inbound submit_audit from them, we could not answer either
way: zero refusals is equally consistent with "nothing arrived" and "it
arrived and was recorded nowhere".

Precondition 2 of 2 for the graded rematch.
"""

import hashlib
import json

from mcp_server import audit_check, wire_v3, wire_v3_session
from mcp_server.interop import NONCE_SEPARATOR, canonical_str
from scripts.reference_artifacts import build_log

IDS = {"game_uid": "uid-1", "game_id": "THEM-vs-aviayeli"}


def _record(step, payload=None):
    """One disclosed record, sealed the way the wire seals it."""
    body = payload or {"step": step, "move": "MOVE:N", "sender": "thief"}
    nonce = f"{step:032x}"
    commit = hashlib.sha256(
        f"{canonical_str(body)}{NONCE_SEPARATOR}{nonce}".encode()).hexdigest()
    return {"payload": body, "nonce": nonce, "commit": commit}


def _audit(records, sender="thief", claim="survival"):
    return {"sender": sender, "records": records, "result_claim": claim}


def _summary(**over):
    base = {
        "sub_game": 1, "role": "police", "result_claim": {"outcome": "survival"},
        "their_audit_response": {"ok": True},
        "handshake_counter_signed": True,
        "our_chain": [], "their_turns": [],
    }
    base.update(over)
    return base


# --- the load-bearing case --------------------------------------------------

def test_an_accepted_inbound_audit_is_persisted_to_the_log(tmp_path):
    records = [_record(1), _record(2)]
    audits = [{**_audit(records), "verdict": {"status": "accepted"}}]

    log = build_log(IDS, _summary(their_disclosed_audits=audits),
                    "aviayeli", barriers=[])

    path = tmp_path / "log.json"
    path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    written = json.loads(path.read_text(encoding="utf-8"))

    assert written["their_disclosed_audits"], "their chain reached no file"
    assert written["their_disclosed_audits"][0]["verdict"]["status"] == "accepted"
    assert len(written["their_disclosed_audits"][0]["records"]) == 2


def test_the_persisted_records_are_byte_identical_to_what_arrived(tmp_path):
    """They are preimages of digests the opponent pushed. Re-serialising them
    destroys the only evidence that lets anyone recheck our verdict."""
    records = [_record(1), _record(2)]
    audits = [{**_audit(records), "verdict": {"status": "accepted"}}]

    log = build_log(IDS, _summary(their_disclosed_audits=audits),
                    "aviayeli", barriers=[])
    path = tmp_path / "log.json"
    path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    persisted = json.loads(path.read_text())["their_disclosed_audits"][0]["records"]
    assert persisted == records

    # and they still re-hash, which is the whole point of keeping them
    for record in persisted:
        assert audit_check.verify_records([record], []) is not None


def test_a_sub_game_with_no_inbound_audit_persists_an_empty_list():
    """Absent and empty must not look alike: this whole defect was an absence
    that could not be told from anything else."""
    log = build_log(IDS, _summary(their_disclosed_audits=[]),
                    "aviayeli", barriers=[])

    assert "their_disclosed_audits" in log
    assert log["their_disclosed_audits"] == []


def test_a_missing_key_still_persists_a_list_not_none():
    """An older summary must not write null, which is indistinguishable from
    an artifact predating the field."""
    log = build_log(IDS, _summary(), "aviayeli", barriers=[])

    assert log["their_disclosed_audits"] == []


# --- what must NOT be persisted --------------------------------------------

def test_a_refused_audit_never_enters_the_record():
    """submit_audit appends AFTER validation. A refused payload never entered
    the record and must not start now."""
    refused = {"sender": "", "records": [], "result_claim": "survival"}

    assert wire_v3_session.validate_audit_payload(refused) != wire_v3.ACCEPT
