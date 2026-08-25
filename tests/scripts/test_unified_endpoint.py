"""Both our roles behind one port and one /mcp route (PRD_11b).

Two tunnels means handing an opponent two URLs plus a rule for choosing
between them — dial the endpoint serving the role you are playing *against* —
and getting it backwards is not a crash: it sends a whole sub-game to a peer
playing the same side, silent on both ends for thirty-five steps.

The routing key is OURS, not theirs, and that is forced by the code rather
than chosen. `negotiate` may legally omit `role`
(`wire_v3_session.NEGOTIATE_OPTIONAL`), so the one message that opens a
sub-game is the one that cannot be routed by what the opponent claims. And
deriving our side from theirs would make `pairing.pairing_refusal`
tautological, destroying the only mispairing check in the system.
"""

import asyncio

import pytest

from mcp_server import interop
from mcp_server.server import PEER_ROLES, create_app
from mcp_server.unified import create_unified_app

TOOLS = ("negotiate", "receive_turn", "submit_audit", "receive_control")


@pytest.fixture
def unified():
    return create_unified_app()


def _turn(sender, step=1):
    return {"step": step, "sender": sender, "hint": "moving",
            "smell_grid": {"3,3": 0.8}, "commit": "a" * 64,
            "timestamp": "2026-08-25T10:00:00+00:00"}


def _handshake(app, role=None):
    terms = app.peers["police"].terms
    nonce = "b" * 32
    message = {"terms": dict(terms), "nonce": nonce,
               "signature": interop.terms_signature(terms, nonce)}
    if role is not None:
        message["role"] = role
    return message


# --- one port, all four tools ----------------------------------------------


def test_the_unified_app_serves_every_reference_v3_tool(unified):
    for name in TOOLS:
        assert callable(getattr(unified, name, None)), name


def test_the_unified_port_comes_from_config_not_a_literal(unified):
    """FR6. A port inlined in source is the hardcoded tunable the constitution
    exists to prevent."""
    assert unified.port == unified.peers["police"].binding.unified_port
    assert unified.port not in (8801, 8802), "that is a split-port listener"


# --- dispatch follows OUR side, and swaps with it --------------------------


def test_a_turn_lands_in_the_inbox_of_the_side_we_are_playing(unified):
    unified.set_active("police")

    reply = asyncio.run(unified.receive_turn(message=_turn("thief")))

    assert reply["status"] == "accepted"
    assert len(unified.peers["police"].inbox) == 1
    assert unified.peers["thief"].inbox == []


def test_the_sides_swap_and_the_same_tool_follows(unified):
    unified.set_active("thief")

    asyncio.run(unified.receive_turn(message=_turn("police")))

    assert len(unified.peers["thief"].inbox) == 1
    assert unified.peers["police"].inbox == []


def test_the_active_role_must_be_a_real_role(unified):
    with pytest.raises(ValueError):
        unified.set_active("cop")


# --- the self-dial that only one port makes possible (FR4) -----------------


def test_a_turn_from_our_own_side_is_refused_and_not_stored(unified):
    """On two ports this could not arrive. On one it is what a self-dial looks
    like — `--opponent-url` pointed at our own tunnel."""
    unified.set_active("police")

    reply = asyncio.run(unified.receive_turn(message=_turn("police")))

    assert reply["status"] == "refused"
    assert "police" in reply["reason"]
    assert unified.peers["police"].inbox == []
    assert unified.peers["thief"].inbox == []


# --- the handshake still checks the pairing (FR3) --------------------------


def test_a_handshake_declaring_our_own_role_is_still_refused(unified):
    """The check the obvious design would have silently destroyed."""
    unified.set_active("police")

    reply = asyncio.run(unified.negotiate(message=_handshake(unified, "police")))

    assert reply.get("status") == "refused"
    assert "pairing" in reply["reason"]


def test_a_handshake_with_no_role_at_all_is_still_answered(unified):
    """`role` is in NEGOTIATE_OPTIONAL; refusing its absence would break a
    conformant peer."""
    unified.set_active("police")

    reply = asyncio.run(unified.negotiate(message=_handshake(unified)))

    assert reply.get("status") == "accepted"
    assert reply["role"] == "police", "we answer as the side WE play"


# --- and the split-port path is untouched (FR5) ----------------------------


def test_the_two_port_apps_are_unchanged(unified):
    for role in PEER_ROLES:
        app = create_app(role)

        assert app.binding.my_port in (8801, 8802)
        assert app.inbox == []
        for name in TOOLS:
            assert callable(getattr(app, name, None)), (role, name)
