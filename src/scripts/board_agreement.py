"""Refuse to start a match the peers cannot both play (audit T-1).

Split out of ``match_loop`` because it is a PRE-match precondition, not
turn logic: it runs once, before either peer has signed anything, and the
module was at the 150-line limit.
"""

class BoardMismatchError(RuntimeError):
    """The peers are not playing the same board, so no match is possible.

    Distinct from DivergenceError: that reports engines disagreeing about a
    position mid-match, which is a symptom. This is the cause, and it is
    detectable BEFORE either peer signs anything.
    """


ENGINE_ROLES = ("cop", "thief")


async def verify_board_agreement(
    connections, expected_barriers: int, roles=ENGINE_ROLES
) -> None:
    """Refuse to start unless every peer reports OUR board (audit T-1).

    `barrier_seed` is an optional extension to the agreed contract, so a peer
    that never heard of it plays a bare board. Left unchecked that surfaces as
    a DivergenceError on turn 1, after commitments are signed, blaming
    positions for a mismatched contract.

    Raises:
        BoardMismatchError: any peer reports a different barrier count.
    """
    for index, (connection, role) in enumerate(zip(connections, roles)):
        # Each peer answers ONLY for its own engine role; asking the thief
        # peer about the cop returns an `invalid_role` error with no board
        # in it, which would read as a mismatch rather than a bad question.
        observed = await connection.get_observation(role)
        reported = observed.get("barrier_count")
        if reported != expected_barriers:
            raise BoardMismatchError(
                f"peer {index} reports {reported} barriers, this engine has "
                f"{expected_barriers}; the peers are not playing the same "
                "board. Check `barrier_seed` in the shared game.json — it is "
                "an OPTIONAL extension and a peer without it plays bare."
            )
