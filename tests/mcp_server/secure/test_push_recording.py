"""What the push dialect RECORDS, and what it refuses to conclude.

The gate that keeps this surface off the wire by default lives in
`test_push_surface.py`; this file assumes it is on and covers behaviour.

The audit tests are the important ones. Their nonces arrive with no payload
attached, so there is nothing to re-hash against — and this dialect must say
`unverifiable`, not `accepted`. A green light we never computed would be worse
than no light at all.
"""

import asyncio

import pytest

from mcp_server.server import create_app

COMMIT = "a" * 64

# Unlike reference-v3's single envelope argument, the push dialect is FLAT:
# their tools/list shows receive_commit(role, step, h_commit). Their client
# calls us with those names, so our signatures must match theirs exactly.


@pytest.fixture
def push_app(secure_config_root):
    return create_app("police", config_root=secure_config_root, dialect="push")


# --- recording -------------------------------------------------------------


def test_a_commit_is_recorded_under_its_step(push_app):
    result = asyncio.run(push_app.receive_commit(
        role="thief", step=4, h_commit=COMMIT))

    assert result["status"] == "accepted"
    assert push_app.push.commits[4] == COMMIT


def test_a_reveal_is_recorded_without_a_nonce(push_app):
    asyncio.run(push_app.receive_reveal(
        role="thief", step=4, move="MOVE:N", hint="", intent="truth"))

    assert push_app.push.reveals[4]["move"] == "MOVE:N"
    assert "nonce" not in push_app.push.reveals[4]


def test_a_refused_message_records_nothing(push_app):
    before = dict(push_app.push.commits)

    result = asyncio.run(push_app.receive_commit(
        role="thief", step=4, h_commit="NOT-HEX"))

    assert result["status"] == "refused"
    assert result["reason"] == "h_commit: required 64-char lowercase hex"
    assert push_app.push.commits == before


def test_an_ack_touches_no_engine_state(push_app):
    turn_before = push_app.match_state.turn_count

    assert asyncio.run(
        push_app.receive_ack(role="thief", step=1))["status"] == "ok"
    assert push_app.match_state.turn_count == turn_before


def test_the_final_audit_reports_unverifiable_when_it_cannot_rebuild(push_app):
    """The test that stops us shipping a green light we never computed.

    Their `nonces` carry no payloads, so there is nothing to re-hash against.
    Reporting `accepted` here would assert an audit we did not run.
    """
    asyncio.run(push_app.receive_commit(role="thief", step=1, h_commit=COMMIT))

    result = asyncio.run(push_app.receive_final_audit(
        role="thief", nonces=["deadbeef"]))

    assert result["status"] == "unverifiable"
    assert result["verified"] == 0
    assert "payload" in result["reason"]


def test_an_audit_that_CAN_be_rebuilt_is_actually_checked(push_app):
    """When the entries carry payloads, we re-hash them with our serializer."""
    from mcp_server import interop

    payload = {"step": 1, "move": "MOVE:N"}
    nonce = "112233445566778899aabbccddeeff00"
    asyncio.run(push_app.receive_commit(
        role="thief", step=1, h_commit=interop.commit(payload, nonce)))

    result = asyncio.run(push_app.receive_final_audit(
        role="thief", nonces=[{"step": 1, "nonce": nonce, "payload": payload}]))

    assert result["status"] == "accepted"
    assert result["verified"] == 1
    assert result["mismatches"] == []


def test_a_rebuilt_audit_catches_a_tampered_record(push_app):
    from mcp_server import interop

    payload = {"step": 1, "move": "MOVE:N"}
    nonce = "ab"
    asyncio.run(push_app.receive_commit(
        role="thief", step=1, h_commit=interop.commit(payload, nonce)))

    result = asyncio.run(push_app.receive_final_audit(
        role="thief",
        nonces=[{"step": 1, "nonce": nonce, "payload": {"step": 1, "move": "MOVE:S"}}]))

    assert result["status"] == "tampered"
    assert result["mismatches"] == [1]
