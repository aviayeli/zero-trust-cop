"""The pairing checks the handshake is the only place to make (SPEC 7.2).

Split from ``wire_v3_session``: that module validates message SHAPE, this
decides whether a well-formed handshake describes a game we may play.

Identical terms give identical ``game_uid``s, so by the time an artifact
exists a mispairing is invisible -- two peers that disagree about which side
they play, or which sub-game they are in, both seal and both settle and both
write consistent-looking files under one uid.

Every check tolerates absence. These are negotiate EXTRAS, and a value that
cannot be compared is treated as silence, which is the kit's own truth table.
"""

from __future__ import annotations


def pairing_refusal(message: dict, our_role: str, our_uid: str | None,
                    our_sub_game: int | None = None) -> str | None:
    """Why this pairing must not start, or None.

    The handshake is the ONLY place a mispairing can be caught. Identical
    terms give identical ``game_uid``s, so two peers that both believe they
    are the thief agree on every signed byte and produce artifacts that join
    perfectly -- the contradiction surfaces only when a human reads the
    result.

    Every check TOLERATES absence: the pairing fields are negotiate extras,
    declaring the uid is PROPOSED, and a value that cannot be compared is
    treated as silence -- the truth table's own last row. Only a declared
    CONTRADICTION is refused.
    """
    their_role = message.get("role")
    if their_role is not None and their_role == our_role:
        other = "thief" if our_role == "police" else "police"
        return (
            f"pairing: both peers declare role {our_role!r}. One must be "
            f"{our_role!r} and the other {other!r}. Note the field's meaning: "
            "`role` is the side THIS peer is playing, NOT the side of the peer "
            "being called. If you are declaring the role of the endpoint you "
            "dialled, invert it. If you meant your own side, you have the "
            "wrong endpoint -- our two peers listen on different ports."
        )

    # SPEC 7.2's truth table: "sub-game numbers differ -> refuse; one game
    # cannot carry two indices". We implemented the role half and not this
    # one, so rstabcde counted their own attempts while we counted position
    # in our series -- both peers sealed, both audits came back clean, and
    # the two reports describe one game under one game_uid with two indices.
    # The handshake is the only place that can be caught.
    theirs = message.get("sub_game_number")
    if (our_sub_game is not None and isinstance(theirs, int)
            and not isinstance(theirs, bool) and theirs != our_sub_game):
        return (
            f"sub_game_number differs: ours {our_sub_game}, theirs {theirs}. "
            "One game cannot carry two indices (SPEC 7.2). Number the "
            "sub-game by its position in the SERIES, counting every sub-game "
            "both peers play, not by how many attempts your own side has "
            "made."
        )

    declared = message.get("game_uid")
    if our_uid and declared and declared != our_uid:
        return (
            f"game_uid mismatch: ours {our_uid}, theirs {declared}. One side "
            "derived it from something other than the flat negotiated terms; "
            "a uid from the whole config is self-consistent across that "
            "peer's own artifacts and fails only the cross-team join."
        )
    return None
