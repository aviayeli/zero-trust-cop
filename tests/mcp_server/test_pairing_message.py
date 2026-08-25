"""The pairing refusal must be true under both topologies (PRD_11b follow-up).

The message ends "our two peers listen on different ports", which is true of
the split-port topology and FALSE of the unified one, where both roles answer
one port by design. It is the same string in both, so it cannot claim either.

Small, but this text is the only diagnostic an opposing team gets at the one
moment a mispairing can be caught -- and a sentence that sends them looking for
a second port that does not exist costs a live window.
"""

import pytest

from mcp_server.pairing import pairing_refusal


@pytest.mark.parametrize("role", ["police", "thief"])
def test_a_collision_is_still_refused(role):
    """The behaviour, unchanged."""
    refusal = pairing_refusal({"role": role}, role, None)

    assert refusal and "pairing" in refusal


def test_the_message_names_both_roles(role="police"):
    refusal = pairing_refusal({"role": role}, role, None)

    assert "'police'" in refusal and "'thief'" in refusal


def test_it_still_explains_which_way_round_role_means():
    """The mistake it exists to correct: declaring the side of the peer you
    dialled rather than the side you are playing."""
    refusal = pairing_refusal({"role": "police"}, "police", None)

    assert "THIS peer is playing" in refusal
    assert "invert it" in refusal


def test_it_does_not_claim_a_topology_it_cannot_know():
    """False under the unified endpoint, where both roles share one port."""
    refusal = pairing_refusal({"role": "police"}, "police", None)

    assert "different ports" not in refusal
    assert "listen on different" not in refusal


def test_a_matching_pair_is_not_refused():
    assert pairing_refusal({"role": "thief"}, "police", None) is None
