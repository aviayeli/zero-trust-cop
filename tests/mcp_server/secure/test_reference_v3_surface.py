"""Both dialects answer on one server, and reference-v3 refuses before it acts.

Our native surface (`submit_commitment` / `reveal_move` / `get_observation` /
`get_match_status`) and the league's reference-v3 surface (`negotiate` /
`receive_turn` / `submit_audit` / `receive_control`) are served side by side,
so an opponent on either dialect can reach us.

Compare tool LISTS before comparing anything inside them: two peers can agree
all fourteen terms, verify each other's signatures and bring up both tunnels,
and still exchange nothing because their surfaces intersect only at
`negotiate` — which is what cost best2934 a scheduled friendly (kit issue #45).
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

REFERENCE_V3 = {"negotiate", "receive_turn", "submit_audit", "receive_control"}
OUR_DIALECT = {"submit_commitment", "reveal_move", "get_observation",
               "get_match_status"}


@pytest.fixture
def tool_names(app):
    async def fetch():
        return {tool.name for tool in await app.mcp.list_tools()}

    return asyncio.run(fetch())

def test_both_dialects_are_served_by_one_peer(tool_names):
    assert REFERENCE_V3 <= tool_names
    assert OUR_DIALECT <= tool_names


def test_tools_list_is_the_liveness_probe_not_a_hello(tool_names):
    """A peer implementing none of our names is still UP; `negotiate` is the
    authority on whether you may play. So there is no `hello` to call."""
    assert "hello" not in tool_names


def test_there_is_no_step_zero_tool(tool_names):
    """The declaration rides in `negotiate` under `identity`; the sealed
    step-0 record is disclosed inside `submit_audit`. A peer that waits for a
    step-0 call waits forever."""
    assert "declare_step0" not in tool_names


# --- negotiate + receive_control -------------------------------------------


def test_negotiate_verifies_their_signature_and_answers_signed(app):
    ours = _our_terms(app)
    nonce = "00112233445566778899aabbccddeeff"
    reply = asyncio.run(app.negotiate(
        terms=ours, nonce=nonce, signature=interop.terms_signature(ours, nonce),
        identity={"group_name": "ali-ahm1"}, sub_game_number=1, role="thief",
    ))

    assert reply["status"] == "accepted"
    assert reply["terms"] == ours
    assert interop.terms_signature(reply["terms"], reply["nonce"]) == reply["signature"]
    assert reply["identity"]["wire_shape"] == "reference-v3"


def test_the_pairing_fields_ride_beside_the_terms_never_inside(app):
    """The terms are a flat signed set; an extra key breaks the signature."""
    ours = _our_terms(app)
    nonce = "ab"
    reply = asyncio.run(app.negotiate(
        terms=ours, nonce=nonce, signature=interop.terms_signature(ours, nonce),
        identity={}, sub_game_number=4, role="police"))

    assert reply["sub_game_number"] == 4 and reply["role"] == "police"
    assert "sub_game_number" not in reply["terms"] and "role" not in reply["terms"]


def test_negotiate_refuses_a_signature_that_does_not_verify(app):
    reply = asyncio.run(app.negotiate(
        terms=_our_terms(app), nonce="ab", signature="0" * 64,
        identity={}, sub_game_number=1, role="thief"))

    assert reply["status"] == "refused"
    assert "signature" in reply["reason"]


def test_negotiate_names_the_term_that_disagrees(app):
    """A bare "mismatch" sends both sides diffing fourteen values that agree."""
    theirs = dict(_our_terms(app), board_size=11)
    nonce = "ab"

    reply = asyncio.run(app.negotiate(
        terms=theirs, nonce=nonce,
        signature=interop.terms_signature(theirs, nonce),
        identity={}, sub_game_number=1, role="thief"))

    assert reply["status"] == "refused"
    assert "board_size" in reply["reason"]


def test_control_answers_without_touching_game_state(app):
    turn_before = app.match_state.turn_count

    reply = asyncio.run(app.receive_control({"kind": "status", "sender": "thief"}))

    assert reply["status"] == "ok"
    assert app.match_state.turn_count == turn_before
