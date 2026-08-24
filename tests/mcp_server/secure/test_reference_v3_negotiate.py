"""`negotiate` and `receive_control`: opening the sub-game, and status.

Every tool on this wire takes ONE envelope argument. The kit's client wraps
its arguments under a single key, so a tool declaring flat parameters fails
Pydantic validation on the CALLER's side before our code is ever reached --
the arity is part of the contract, not an implementation detail.

The tool listing itself lives in `test_reference_v3_surface.py`, and the
per-turn messages in `test_reference_v3_turns.py`.
"""

import asyncio
import json
from pathlib import Path

import pytest

from mcp_server import interop
from mcp_server.terms import terms_from_config


def _our_terms(app):
    return terms_from_config(
        json.loads(Path(app.config_path).read_text(encoding="utf-8"))
    )


@pytest.fixture
def tool_schemas(app):
    async def fetch():
        return {tool.name: tool.inputSchema for tool in await app.mcp.list_tools()}

    return asyncio.run(fetch())


# --- negotiate + receive_control -------------------------------------------


def test_negotiate_verifies_their_signature_and_answers_signed(app):
    ours = _our_terms(app)
    nonce = "00112233445566778899aabbccddeeff"
    reply = asyncio.run(app.negotiate({
        "terms": ours, "nonce": nonce,
        "signature": interop.terms_signature(ours, nonce),
        "identity": {"group_name": "ali-ahm1"},
        "sub_game_number": 1, "role": "thief",
    }))

    assert reply["status"] == "accepted"
    assert reply["terms"] == ours
    assert interop.terms_signature(reply["terms"], reply["nonce"]) == reply["signature"]
    assert reply["identity"]["wire_shape"] == "reference-v3"


def test_the_pairing_fields_ride_beside_the_terms_never_inside(app):
    """The terms are a flat signed set; an extra key breaks the signature."""
    ours = _our_terms(app)
    nonce = "ab"
    reply = asyncio.run(app.negotiate({
        "terms": ours, "nonce": nonce,
        "signature": interop.terms_signature(ours, nonce),
        "identity": {}, "sub_game_number": 4, "role": "thief"}))

    assert reply["sub_game_number"] == 4 and reply["role"] == "thief"
    assert "sub_game_number" not in reply["terms"] and "role" not in reply["terms"]


def test_negotiate_refuses_a_signature_that_does_not_verify(app):
    reply = asyncio.run(app.negotiate({
        "terms": _our_terms(app), "nonce": "ab", "signature": "0" * 64,
        "identity": {}, "sub_game_number": 1, "role": "thief"}))

    assert reply["status"] == "refused"
    assert "signature" in reply["reason"]


def test_negotiate_names_the_term_that_disagrees(app):
    """A bare "mismatch" sends both sides diffing fourteen values that agree."""
    theirs = dict(_our_terms(app), board_size=11)
    nonce = "ab"

    reply = asyncio.run(app.negotiate({
        "terms": theirs, "nonce": nonce,
        "signature": interop.terms_signature(theirs, nonce),
        "identity": {}, "sub_game_number": 1, "role": "thief"}))

    assert reply["status"] == "refused"
    assert "board_size" in reply["reason"]


def test_control_answers_without_touching_game_state(app):
    turn_before = app.match_state.turn_count

    reply = asyncio.run(app.receive_control({"kind": "status", "sender": "thief"}))

    assert reply["status"] == "ok"
    assert app.match_state.turn_count == turn_before


def test_every_reference_tool_takes_ONE_envelope_argument(tool_schemas):
    """The kit's client wraps all arguments in a single envelope key. A tool
    with flat parameters raises a Pydantic validation error on their side
    before our code ever runs, so the arity is the wire contract."""
    assert list(tool_schemas["negotiate"]["properties"]) == ["message"]
    assert list(tool_schemas["receive_turn"]["properties"]) == ["message"]
    assert list(tool_schemas["receive_control"]["properties"]) == ["message"]
    assert list(tool_schemas["submit_audit"]["properties"]) == ["payload"]


def test_negotiate_refuses_a_malformed_envelope_without_raising(app):
    """A refusal they can read beats a stack trace they cannot."""
    for junk in ({}, {"terms": {}}, [], None, "negotiate"):
        reply = asyncio.run(app.negotiate(junk))
        assert reply["status"] == "refused"
        assert reply["reason"]


def test_negotiate_tolerates_an_unknown_envelope_key(app):
    """Same extension seam as every other message on this wire."""
    ours = _our_terms(app)
    nonce = "ab"
    reply = asyncio.run(app.negotiate({
        "terms": ours, "nonce": nonce,
        "signature": interop.terms_signature(ours, nonce),
        "future_field": {"anything": 1}}))

    assert reply["status"] == "accepted"


def test_the_optional_envelope_fields_may_be_absent(app):
    """`identity`, `sub_game_number` and `role` are extras, not requirements."""
    ours = _our_terms(app)
    nonce = "ab"
    reply = asyncio.run(app.negotiate({
        "terms": ours, "nonce": nonce,
        "signature": interop.terms_signature(ours, nonce)}))

    assert reply["status"] == "accepted"
    assert reply["sub_game_number"] is None and reply["role"] is None
