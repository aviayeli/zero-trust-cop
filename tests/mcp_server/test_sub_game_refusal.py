"""Two peers cannot be in two sub-games at once (SPEC §7.2, PRD_10 10.28).

The kit's truth table is explicit:

    | same sub-game, complementary roles      | play   |
    | sub-game numbers differ                 | REFUSE |
    | both declare the same role              | refuse |
    | either side omits either field          | play   |
    | a declared value cannot be compared     | play   |

We implemented the role half and not this one: we echoed their number back
and played on. So rstabcde counted their own attempts (their cop's second
attempt = "4") while we counted position in our series ("2"), both peers
sealed, both audits came back clean, and the two reports describe one game
under one `game_uid` with two different indices.

That is the failure §7.2 exists to prevent, in its own words: "by the time an
artifact exists, a mispairing is already invisible." The handshake is the
only place it can be caught, and we were not catching it.

Omission still plays. `sub_game_number` is a negotiate EXTRA, and a peer that
declares nothing is not in disagreement with us.
"""


from mcp_server.wire_v3_session import pairing_refusal


def _reply(**extra):
    return dict({"role": "thief"}, **extra)


def test_the_same_index_plays():
    assert pairing_refusal(_reply(sub_game_number=2), "police", None,
                           our_sub_game=2) is None


def test_a_different_index_is_refused():
    refusal = pairing_refusal(_reply(sub_game_number=4), "police", None,
                              our_sub_game=2)

    assert refusal is not None
    assert "4" in refusal and "2" in refusal


def test_the_refusal_names_both_numbers_not_just_a_mismatch():
    """A bare 'mismatch' sends both sides guessing which counter is wrong."""
    refusal = pairing_refusal(_reply(sub_game_number=4), "police", None,
                              our_sub_game=2)

    assert "sub_game_number" in refusal


def test_their_omission_still_plays():
    """A negotiate EXTRA. A peer that declares nothing disagrees with nobody."""
    assert pairing_refusal(_reply(), "police", None, our_sub_game=2) is None


def test_our_own_omission_still_plays():
    assert pairing_refusal(_reply(sub_game_number=4), "police", None) is None


def test_a_value_that_cannot_be_compared_plays():
    """The table's last row: treated as silence, never as disagreement."""
    assert pairing_refusal(_reply(sub_game_number="two"), "police", None,
                           our_sub_game=2) is None


def test_the_role_collision_still_refuses():
    """The half we already had must keep working."""
    refusal = pairing_refusal(_reply(role="police", sub_game_number=2),
                              "police", None, our_sub_game=2)

    assert refusal is not None and "role" in refusal
