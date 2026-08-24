"""reference-v3 message handling: one TurnMessage in, one audit out.

The receiving half of SPEC §7.5. Two properties are load-bearing and easy to
lose: validation runs BEFORE any state change (so a refusal never leaves a
half-applied turn behind), and the audit re-hashes the opponent's revealed
chain with OUR serializer — their `result_claim` is a claim, our recomputation
is the evidence.

The surface itself, `negotiate` and `receive_control` live in
`test_reference_v3_surface.py`.
"""

import asyncio
import json
from pathlib import Path

import pytest

from mcp_server import interop
from mcp_server.terms import terms_from_config

FIXTURE = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "interop" / "turn_message.json")
    .read_text(encoding="utf-8")
)
GOOD_TURN = FIXTURE["validation"][0]["message"]
REFUSALS = [c for c in FIXTURE["validation"] if c["verdict"] != "accept"]


def _our_terms(app):
    return terms_from_config(
        json.loads(Path(app.config_path).read_text(encoding="utf-8"))
    )


# --- receive_turn ----------------------------------------------------------


def test_a_valid_turn_is_accepted_and_reaches_the_inbox(app):
    result = asyncio.run(app.receive_turn(dict(GOOD_TURN)))

    assert result["status"] == "accepted"
    assert result["step"] == GOOD_TURN["step"]
    assert app.inbox[-1]["commit"] == GOOD_TURN["commit"]


def test_an_unknown_key_is_tolerated(app):
    """The extension seam: a receiver that refuses unknown keys cannot be
    extended without a flag day."""
    result = asyncio.run(app.receive_turn(dict(GOOD_TURN, unknown_field={"a": 1})))

    assert result["status"] == "accepted"


@pytest.mark.parametrize(
    "case", [pytest.param(c, id=c["verdict"][:40]) for c in REFUSALS]
)
def test_a_refused_turn_names_the_published_reason(app, case):
    result = asyncio.run(app.receive_turn(case["message"]))

    assert result["status"] == "refused"
    assert result["reason"] == case["verdict"]


def test_a_refused_turn_changes_no_state(app):
    """Validation happens BEFORE any state change, so a refusal never leaves
    a half-applied turn behind."""
    before = list(app.inbox)

    asyncio.run(app.receive_turn(dict(GOOD_TURN, commit="NOT-HEX")))

    assert list(app.inbox) == before


# --- submit_audit ----------------------------------------------------------


def test_an_audit_is_rehashed_with_our_own_serializer(app):
    """The point of the audit: we re-hash their revealed chain with OUR
    canonicalization. Agreement is the evidence; their claim is not."""
    payload = {"step": 1, "move": "MOVE:N", "hint": "אני ליד הכיכר 🙂"}
    nonce = "112233445566778899aabbccddeeff00"
    result = asyncio.run(app.submit_audit({
        "sender": "thief",
        "result_claim": {"outcome": "capture"},
        "records": [{"step": 1, "payload": payload, "nonce": nonce,
                     "commit": interop.commit(payload, nonce)}],
    }))

    assert result["status"] == "accepted"
    assert result["records_verified"] == 1
    assert result["mismatches"] == []


def test_a_tampered_record_in_the_agreed_shape_is_named_not_a_crash(app):
    """The agreed record is {payload, nonce, commit} with NO top-level step.
    Indexing one crashed the tamper path while the honest path passed — the
    wrong way round, since the tamper path is the one that has to work."""
    good = {"step": 1, "move": "MOVE:N"}
    nonce = "ab"
    result = asyncio.run(app.submit_audit({
        "sender": "thief",
        "result_claim": {},
        "records": [
            {"payload": good, "nonce": nonce, "commit": interop.commit(good, nonce)},
            {"payload": {"step": 2, "move": "MOVE:S"}, "nonce": nonce,
             "commit": "b" * 64},
        ],
    }))

    assert result["status"] == "tampered"
    assert result["mismatches"] == [2]


def test_a_tampered_record_is_named_even_with_no_step_anywhere(app):
    """Fall back to position in the chain rather than raising."""
    result = asyncio.run(app.submit_audit({
        "sender": "thief", "result_claim": {},
        "records": [{"payload": {"move": "MOVE:N"}, "nonce": "ab",
                     "commit": "c" * 64}],
    }))

    assert result["status"] == "tampered"
    assert result["mismatches"] == [1]


def test_a_malformed_audit_is_refused_before_rehashing(app):
    result = asyncio.run(app.submit_audit(
        {"sender": "thief", "records": [], "result_claim": {}}))

    assert result["status"] == "refused"
    assert result["reason"] == "records: required non-empty list"
