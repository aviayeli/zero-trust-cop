"""The handshake is the ONLY place a mispairing can be caught.

Identical terms give identical `game_uid`s, so two peers that both believe
they are the thief agree on every signed byte and produce artifacts that join
perfectly — the contradiction only surfaces when a human reads the result.
`negotiate` is therefore where role complementarity has to be asserted.

Observed live on 2026-08-24: ali-ahm1 declared `role: thief` to OUR thief peer
(they had been handed the wrong tunnel URL) and we answered `accepted`. Every
term matched and both sides derived the same uid, so nothing else in the stack
had any reason to object.
"""

import asyncio
import json
from pathlib import Path

import pytest

from mcp_server import interop
from mcp_server.server import create_app
from mcp_server.terms import terms_from_config

THEM = "ali-ahm1"


def _envelope(app, role, **extra):
    terms = terms_from_config(
        json.loads(Path(app.config_path).read_text(encoding="utf-8")))
    nonce = "00112233445566778899aabbccddeeff"
    return {
        "terms": terms, "nonce": nonce,
        "signature": interop.terms_signature(terms, nonce),
        "identity": {"group_name": THEM}, "group_id": THEM,
        "sub_game_number": 1, "role": role, **extra,
    }


@pytest.fixture
def thief_app(secure_config_root):
    return create_app("thief", config_root=secure_config_root)


def test_a_complementary_pairing_is_accepted(app):
    """`app` is our POLICE peer, so an opposing thief is the right pairing."""
    reply = asyncio.run(app.negotiate(_envelope(app, "thief")))

    assert reply["status"] == "accepted"


def test_two_peers_claiming_the_same_role_are_refused(thief_app):
    reply = asyncio.run(thief_app.negotiate(_envelope(thief_app, "thief")))

    assert reply["status"] == "refused"
    assert "role" in reply["reason"]


def test_the_refusal_names_both_sides_rather_than_saying_mismatch(thief_app):
    reply = asyncio.run(thief_app.negotiate(_envelope(thief_app, "thief")))

    assert "thief" in reply["reason"]
    assert "police" in reply["reason"]


def test_an_absent_role_is_tolerated(app):
    """The pairing fields are extras. A peer that omits them is not refused —
    only a peer that declares a CONTRADICTION is."""
    envelope = _envelope(app, "thief")
    del envelope["role"]

    assert asyncio.run(app.negotiate(envelope))["status"] == "accepted"


# --- the declared uid ------------------------------------------------------


def test_a_declared_uid_that_agrees_is_accepted(app):
    ours = interop.game_uid(app.terms, "aviayeli", THEM)

    reply = asyncio.run(app.negotiate(_envelope(app, "thief", game_uid=ours)))

    assert reply["status"] == "accepted"
    assert reply["game_uid"] == ours


def test_a_declared_uid_that_disagrees_is_refused(app):
    """The silent failure the kit warns about: a uid derived from the whole
    config rather than the flat terms is stable, reproducible, and identical
    across all four of that peer's own artifacts — only the CROSS-team join
    fails, and nothing on either side has reason to look."""
    reply = asyncio.run(app.negotiate(_envelope(app, "thief", game_uid="0" * 36)))

    assert reply["status"] == "refused"
    assert "game_uid" in reply["reason"]


def test_an_absent_uid_is_tolerated(app):
    """Declaring it is PROPOSED, not required — the uid normally never
    crosses the wire at all."""
    assert asyncio.run(app.negotiate(_envelope(app, "thief")))["status"] == "accepted"


# --- our reply must declare OUR side ---------------------------------------


def test_our_reply_declares_our_own_role_not_an_echo_of_theirs(app):
    """The kit defines `role` as "the side THIS peer is playing", so echoing
    the caller's value tells them nothing and hides a collision.

    Observed live 2026-08-24: ali-ahm1 declared the role of the endpoint they
    dialled rather than their own, and our echo meant every reply agreed with
    them — nothing in the exchange said what WE thought we were.
    """
    reply = asyncio.run(app.negotiate(_envelope(app, "thief")))

    assert reply["status"] == "accepted"
    assert reply["role"] == "police"


def test_the_reply_still_echoes_the_sub_game_it_was_asked_about(app):
    """sub_game_number is the index BOTH peers believe they are on, so
    agreeing with the caller is the correct answer there."""
    reply = asyncio.run(app.negotiate(_envelope(app, "thief")))

    assert reply["sub_game_number"] == 1


def test_a_refusal_names_the_two_conflicting_sides(thief_app):
    """The refusal has to be diagnosable from the wire alone."""
    reply = asyncio.run(thief_app.negotiate(_envelope(thief_app, "thief")))

    assert "'thief'" in reply["reason"] and "'police'" in reply["reason"]
    assert "the side THIS peer is playing" in reply["reason"]


def test_a_refusal_still_states_our_own_side(thief_app):
    """A refusal that does not say what WE are leaves the caller guessing
    which half of the pair to change."""
    reply = asyncio.run(thief_app.negotiate(_envelope(thief_app, "thief")))

    assert reply["status"] == "refused"
    assert reply["role"] == "thief"
