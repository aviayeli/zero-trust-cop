"""A proposal must be signed correctly, or it is worse than nothing (Council).

The brief asked for a payload that would be "instantly acceptable by our peer".
It cannot be. `decay_per_step` and `emit_intensity` are two of the FOURTEEN
signed terms (`mcp_server/terms.py`), so a peer running the shipped contract
computes a different terms hash and refuses the handshake by design -- that
refusal is the interop check working, not failing.

So this generates a RENEGOTIATION PROPOSAL: the terms we want, signed so the
opponent can verify we computed what we claim, plus an explicit statement of
what changed and that they must adopt it too. These tests pin the property
that actually matters -- the signature verifies -- and the honesty of the
`changed` block.
"""


import pytest

from mcp_server import interop
from mcp_server.terms import TERMS_KEYS
from scripts.handshake_negotiator import proposal

OPTIMAL = {"pheromones": {"pheromone_decay": 0.25,
                          "pheromone_center_intensity": 0.5}}


@pytest.fixture
def signed():
    return proposal(OPTIMAL, nonce="a" * 32)


def test_the_signature_verifies_over_the_terms_it_carries(signed):
    """The one property a proposal is worthless without."""
    assert interop.terms_signature(signed["terms"], signed["nonce"]) == \
        signed["signature"]


def test_it_carries_all_fourteen_terms(signed):
    """A proposal missing a term hashes to something no peer can reproduce."""
    assert set(signed["terms"]) == set(TERMS_KEYS)


def test_the_overrides_actually_reach_the_terms(signed):
    assert signed["terms"]["decay_per_step"] == 0.25
    assert signed["terms"]["emit_intensity"] == 0.5


def test_nothing_else_is_quietly_altered(signed):
    """A renegotiation that silently moved num_games would be a different
    game, not a different belief model."""
    assert set(signed["changed"]) == {"decay_per_step", "emit_intensity"}
    assert signed["terms"]["num_games"] == 6
    assert signed["terms"]["board_size"] == 7


def test_the_changed_block_reports_both_sides(signed):
    assert signed["changed"]["decay_per_step"] == {"from": 0.1, "to": 0.25}


def test_an_empty_proposal_changes_nothing(signed):
    plain = proposal({}, nonce="b" * 32)

    assert plain["changed"] == {}
    assert interop.terms_signature(plain["terms"], plain["nonce"]) == \
        plain["signature"]


def test_an_unchanged_proposal_matches_what_a_peer_would_compute():
    """The control: with no overrides our signature equals the one a peer
    running the shipped contract produces for the same nonce."""
    import json as _json

    from mcp_server.terms import terms_from_config

    with open("config/game.json") as handle:
        theirs = terms_from_config(_json.load(handle))
    ours = proposal({}, nonce="c" * 32)

    assert ours["terms"] == theirs
    assert ours["signature"] == interop.terms_signature(theirs, "c" * 32)


def test_it_says_out_loud_that_agreement_is_required(signed):
    assert "refused" in signed["note"].lower() or "adopt" in signed["note"].lower()


def test_a_fresh_nonce_is_generated_when_none_is_given():
    """A reused nonce lets an observer link two proposals."""
    first, second = proposal(OPTIMAL), proposal(OPTIMAL)

    assert first["nonce"] != second["nonce"]
    assert len(first["nonce"]) == 32


def test_the_local_only_knob_is_not_smuggled_into_the_terms():
    """`max_consecutive_stay` is private strategy, not a contract term.
    Putting it in the signed set would break every peer's hash."""
    from scripts.handshake_negotiator import main

    main(["--max-consecutive-stay", "2", "--out", "/dev/null"])

    assert "max_consecutive_stay" not in TERMS_KEYS
    # And it must not reach the SIGNED set by any route.
    assert "max_consecutive_stay" not in proposal({}, nonce="d" * 32)["terms"]
