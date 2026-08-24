"""reference-v3 message validation, bound to the league fixture.

Validation happens BEFORE any state change. The two load-bearing cases are
the ones that look like details: an unknown key must be TOLERATED (the
extension seam — a receiver that refuses it cannot be extended without a flag
day), and a missing required key must be REFUSED rather than defaulted, because
a defaulted `commit` is a move the sender never sealed.

The refusal strings are the fixture's own verdicts, so a drift in our wording
is a test failure rather than a silent divergence from the published contract.
"""

import json
from pathlib import Path

import pytest

from mcp_server import wire_v3, wire_v3_session

VECTORS = Path(__file__).parent.parent / "fixtures" / "interop"
FIXTURE = json.loads((VECTORS / "turn_message.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "case",
    [pytest.param(c, id=c["note"][:55]) for c in FIXTURE["validation"]],
)
def test_every_published_validation_case(case):
    assert wire_v3.validate_turn_message(case["message"]) == case["verdict"]


def test_the_required_key_set_matches_the_published_one():
    assert sorted(wire_v3.TURN_REQUIRED) == sorted(FIXTURE["turn_message"]["required"])
    assert sorted(wire_v3.TURN_OPTIONAL) == sorted(FIXTURE["turn_message"]["optional"])


def test_a_step_is_a_round_not_a_half_turn():
    """`max_steps: 35` means 35 moves EACH. Two peers reading this differently
    agree on every signed term and still desync, and no gate catches it."""
    assert "ROUND" in wire_v3.STEP_SEMANTICS
    assert "35 moves EACH" in wire_v3.STEP_SEMANTICS


@pytest.mark.parametrize("sender", ["cop", "POLICE", "", None, 7])
def test_an_unknown_sender_is_refused(sender):
    message = dict(FIXTURE["validation"][0]["message"], sender=sender)

    assert wire_v3.validate_turn_message(message) == "sender: required 'police' | 'thief'"


def test_an_empty_hint_is_accepted_but_a_missing_one_is_not():
    """The hint may be empty, and may be a lie — App. E permits deception in
    the verbal channel. Absent is a different thing from empty."""
    base = FIXTURE["validation"][0]["message"]

    assert wire_v3.validate_turn_message(dict(base, hint="")) == "accept"
    assert wire_v3.validate_turn_message(
        {k: v for k, v in base.items() if k != "hint"}
    ) == "hint: required str"


def test_a_non_mapping_message_is_refused_without_raising():
    for junk in ([], "turn", None, 3):
        assert wire_v3.validate_turn_message(junk) == "message: required object"


# --- audit + control -------------------------------------------------------


def test_the_audit_required_keys_match_the_published_set():
    assert sorted(wire_v3_session.AUDIT_REQUIRED) == sorted(FIXTURE["audit_payload"]["required"])


def test_an_audit_carries_its_nonces():
    """The opponent re-hashes every step with its own serializer, so a chain
    without nonces cannot be audited at all."""
    payload = {"sender": "police", "result_claim": {"outcome": "capture"},
               "records": [{"step": 1, "payload": {"move": "MOVE:N"},
                            "nonce": "ab", "commit": "a" * 64}]}

    assert wire_v3_session.validate_audit_payload(payload) == "accept"
    stripped = {**payload, "records": [{"step": 1, "payload": {}, "commit": "a" * 64}]}
    assert wire_v3_session.validate_audit_payload(stripped) == \
        "records: each record needs payload, nonce, commit"


def test_an_audit_with_no_records_is_refused():
    assert wire_v3_session.validate_audit_payload(
        {"sender": "police", "records": [], "result_claim": {}}
    ) == "records: required non-empty list"


def test_a_control_message_needs_only_kind_and_sender():
    assert sorted(wire_v3_session.CONTROL_REQUIRED) == sorted(
        FIXTURE["control_message"]["required"])
    assert wire_v3_session.validate_control_message(
        {"kind": "status", "sender": "police"}) == "accept"
    assert wire_v3_session.validate_control_message({"kind": "status"}) == \
        "sender: required 'police' | 'thief'"


def test_control_touches_no_game_state():
    """A status channel that is never sealed and never scored."""
    assert wire_v3_session.validate_control_message(
        {"kind": "status", "sender": "thief", "unknown": 1}) == "accept"
