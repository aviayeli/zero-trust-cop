"""Does their peer agree with our contract, and did we actually check (PRD_11)?

Split from `test_netcheck` at the 150-line limit; the seam is real rather than
arithmetic. That module asks whether we can reach them at all, this one asks
whether what came back proves anything — which is where the interesting
failure lives: a peer can answer 200, accept the handshake, and still be
playing a different game.

`num_games` is the term this league has actually disagreed on, and a bare
`{"accepted": true}` is the acceptance ali-ahm1's server really sends.
"""

import pytest
from netcheck_peer import (
    FakePeer,
    load_terms,
    run_probe,
    signed_reply,
    verdict_for,
)

from scripts import netcheck


@pytest.fixture
def our_terms():
    return load_terms()


# --- what a failure has to NAME --------------------------------------------


def test_a_refusal_surfaces_the_reason_the_peer_gave(our_terms):
    peer = FakePeer(reply={"status": "refused", "accepted": False,
                           "reason": "role collision: both police"})

    report = run_probe(peer, our_terms)

    assert verdict_for(report, "handshake")["ok"] is False
    assert "role collision" in verdict_for(report, "handshake")["detail"]
    assert netcheck.exit_code(report) != 0


def test_disagreeing_terms_name_the_term_and_both_values(our_terms):
    """A bare 'terms mismatch' sends both sides diffing fourteen values that
    already agree. This is the one the league has actually hit."""
    peer = FakePeer(reply=signed_reply(dict(our_terms, num_games=3)))

    report = run_probe(peer, our_terms)

    detail = verdict_for(report, "terms")["detail"]
    assert verdict_for(report, "terms")["ok"] is False
    assert "num_games" in detail
    assert "6" in detail and "3" in detail
    assert netcheck.exit_code(report) != 0


def test_a_forged_signature_fails_the_terms_check(our_terms):
    """Terms that agree under a signature that does not verify are terms we
    have no evidence they hold."""
    peer = FakePeer(reply=dict(signed_reply(our_terms), signature="0" * 64))

    report = run_probe(peer, our_terms)

    assert verdict_for(report, "terms")["ok"] is False
    assert "signature" in verdict_for(report, "terms")["detail"]


# --- never assert a check that did not run ---------------------------------


def test_a_bare_acceptance_is_not_a_verified_comparison(our_terms):
    """ali-ahm1's server answers `{"accepted": true}` — a real acceptance
    carrying no terms, no nonce and no signature. Reporting that as a passed
    terms check asserts a comparison that never ran."""
    report = run_probe(FakePeer(reply={"accepted": True}), our_terms)

    assert verdict_for(report, "handshake")["ok"] is True
    assert verdict_for(report, "terms")["ok"] is False
    assert "UNVERIFIED" in verdict_for(report, "terms")["detail"]
    assert netcheck.exit_code(report) != 0


def test_every_live_spelling_of_yes_is_read_as_acceptance(our_terms):
    """Ours is `status`, rstabcde say `accepted`, ZeroOne0 say `ok`. Refusing
    an unfamiliar word for yes would report a healthy peer as dead."""
    for spelling in ({"status": "accepted"}, {"accepted": True}, {"ok": True}):
        report = run_probe(FakePeer(reply=dict(spelling)), our_terms)

        assert verdict_for(report, "handshake")["ok"] is True, spelling


# --- read-only (FR6) -------------------------------------------------------


def test_the_probe_opens_no_sub_game_and_pushes_no_turn(our_terms):
    """Sub-games are 1-indexed in every schedule either side plays, so a
    handshake at 0 cannot collide with a real one."""
    peer = FakePeer(reply=signed_reply(our_terms))

    run_probe(peer, our_terms)

    assert [call[0] for call in peer.calls] == ["list_tools", "negotiate"]
    assert peer.calls[1][1]["message"]["sub_game_number"] == 0
    assert netcheck.PROBE_SUB_GAME == 0


def test_the_probe_signs_the_terms_it_sends(our_terms):
    """The opponent verifies our signature over our terms before answering;
    an unsigned probe would be refused for the wrong reason."""
    from mcp_server import interop

    peer = FakePeer(reply=signed_reply(our_terms))
    run_probe(peer, our_terms)

    sent = peer.calls[1][1]["message"]
    assert sent["signature"] == interop.terms_signature(sent["terms"],
                                                        sent["nonce"])
    assert sent["role"] == "police"
