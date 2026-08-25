"""A refused inbound message must not vanish (PRD_12 FR1-FR3).

`receive_turn` validates, and on failure returns `{"status": "refused", ...}`
WITHOUT appending to the inbox — under HTTP 200, because that is what the tool
layer returns for any completed call. So an opponent watching status codes sees
an unbroken run of 200s while every message they send is dropped, and our own
console shows nothing at all.

That is not hypothetical. On 2026-08-25 bb-ai-12 reported "turns exchange
cleanly, all 200/202 on our side" for a series that advanced past no step at
all.

These tests pin the LOGGING and, just as importantly, pin that nothing else
moved: same return payload, same inbox.
"""

import asyncio
import logging

import pytest

from mcp_server import interop
from mcp_server.server import create_app


@pytest.fixture
def app():
    return create_app("police")


def _turn(**overrides):
    message = {
        "step": 1,
        "sender": "thief",
        "hint": "moving south",
        "smell_grid": {"3,3": 0.8},
        "commit": "a" * 64,
        "timestamp": "2026-08-25T10:00:00+00:00",
    }
    message.update(overrides)
    return message


def _audit(**overrides):
    record = {"step": 1, "state": "grid=7x7;self=[3, 3];barriers=[]",
              "position": [3, 3], "move": "S", "intent": "honest",
              "hint": "moving"}
    nonce = "0" * 32
    payload = {"sender": "thief",
               "records": [{"payload": record, "nonce": nonce,
                            "commit": interop.commit(record, nonce)}],
               "result_claim": {"outcome": "ongoing"}}
    payload.update(overrides)
    return payload


def _messages(caplog):
    return " ".join(record.getMessage() for record in caplog.records)


# --- the refusal is recorded (FR1, FR3) ------------------------------------


def test_a_malformed_turn_is_logged_with_its_reason(app, caplog):
    with caplog.at_level(logging.WARNING):
        asyncio.run(app.receive_turn(message=_turn(smell_grid="not-a-grid")))

    assert caplog.records, "a refused turn left no trace at all"
    assert "smell_grid" in _messages(caplog), _messages(caplog)
    assert "receive_turn" in _messages(caplog), _messages(caplog)


def test_the_log_names_the_step_and_sender_we_refused(app, caplog):
    with caplog.at_level(logging.WARNING):
        asyncio.run(app.receive_turn(message=_turn(step=7, commit=None)))

    logged = _messages(caplog)
    assert "7" in logged and "thief" in logged, logged


def test_a_refused_audit_is_logged_too(app, caplog):
    with caplog.at_level(logging.WARNING):
        asyncio.run(app.submit_audit(payload={"sender": "thief"}))

    logged = _messages(caplog)
    assert "submit_audit" in logged, logged
    assert "records" in logged, logged


# --- and NOTHING else moved (FR2) ------------------------------------------


def test_the_refusal_payload_is_unchanged(app):
    reply = asyncio.run(app.receive_turn(message=_turn(sender="nobody")))

    assert reply["status"] == "refused"
    assert "sender" in reply["reason"]


def test_a_refused_turn_still_never_enters_the_inbox(app):
    asyncio.run(app.receive_turn(message=_turn(smell_grid=None)))

    assert app.inbox == [], "a refused turn was stored"


def test_a_good_turn_is_stored_and_logs_nothing(app, caplog):
    """No false positives: the quiet path must stay quiet."""
    with caplog.at_level(logging.WARNING):
        reply = asyncio.run(app.receive_turn(message=_turn()))

    assert reply["status"] == "accepted"
    assert len(app.inbox) == 1
    assert not caplog.records, [r.getMessage() for r in caplog.records]


def test_a_good_audit_is_accepted_and_logs_nothing(app, caplog):
    with caplog.at_level(logging.WARNING):
        reply = asyncio.run(app.submit_audit(payload=_audit()))

    assert reply["status"] == "accepted"
    assert not caplog.records, [r.getMessage() for r in caplog.records]
