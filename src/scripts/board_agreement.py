"""Refuse to start a match the peers cannot both play (audit T-1).

Split out of ``match_loop`` because it is a PRE-match precondition, not
turn logic: it runs once, before either peer has signed anything, and the
module was at the 150-line limit.
"""

from engine.config import (AXIS_ORIGIN_ALIASES, SUPPORTED_AXIS_ORIGIN,
                           SUPPORTED_AXIS_START)
from mcp_server.observations import scoring_block

class BoardMismatchError(RuntimeError):
    """The peers are not playing the same board, so no match is possible.

    Distinct from DivergenceError: that reports engines disagreeing about a
    position mid-match, which is a symptom. This is the cause, and it is
    detectable BEFORE either peer signs anything.
    """


ENGINE_ROLES = ("cop", "thief")
# Convention fields a peer MAY report. Absent is not disagreement: they are an
# extension, and refusing silence would repeat the `barrier_seed` mistake of
# turning an optional addition into a match that cannot start.
AXIS_FIELDS = ("axis_origin_corner", "axis_start_index")


async def verify_board_agreement(
    connections, expected_barriers: int, config=None, roles=ENGINE_ROLES
) -> None:
    """Refuse to start unless every peer reports OUR board (audit T-1).

    `barrier_seed` is an optional extension to the agreed contract, so a peer
    that never heard of it plays a bare board. Left unchecked that surfaces as
    a DivergenceError on turn 1, after commitments are signed, blaming
    positions for a mismatched contract.

    Raises:
        BoardMismatchError: a peer reports a different board or rule set.
    """
    for index, (connection, role) in enumerate(zip(connections, roles)):
        # Each peer answers ONLY for its own engine role; asking the thief
        # peer about the cop returns an `invalid_role` error with no board
        # in it, which would read as a mismatch rather than a bad question.
        observed = await connection.get_observation(role)
        reported = observed.get("barrier_count")
        _check_axis(index, observed)
        if config is not None:
            _check_rules(index, observed, config)
        if reported != expected_barriers:
            raise BoardMismatchError(
                f"peer {index} reports {reported} barriers, this engine has "
                f"{expected_barriers}; the peers are not playing the same "
                "board. Check `barrier_seed` in the shared game.json — it is "
                "an OPTIONAL extension and a peer without it plays bare."
            )


def _check_axis(index: int, observed: dict) -> None:
    """Compare a peer's coordinate convention against ours, when it states one.

    A mirrored engine does not error — it plays a plausible game that is
    silently the wrong one — so a stated disagreement is fatal here.

    Raises:
        BoardMismatchError: the peer names a convention we do not implement.
    """
    for field in AXIS_FIELDS:
        theirs = observed.get(field)
        if theirs is None:
            continue
        ours = _OURS[field]
        # The ORIGIN has two accepted spellings of one corner; the league
        # writes `top-left` and we used to write `topleft`. A peer on either
        # is on our convention, and refusing one of them would reject a peer
        # that agrees with us over a hyphen.
        if field == "axis_origin_corner" and theirs in AXIS_ORIGIN_ALIASES:
            continue
        if theirs != ours:
            raise BoardMismatchError(
                f"peer {index} reports {field}={theirs!r}, this engine "
                f"implements {ours!r}. Every move would mirror and the match "
                "would look plausible while being the wrong game."
            )


_OURS = {
    "axis_origin_corner": SUPPORTED_AXIS_ORIGIN,
    "axis_start_index": SUPPORTED_AXIS_START,
}


def _check_rules(index: int, observed: dict, config) -> None:
    """Compare the RULES a peer states against ours, when it states them.

    These two fail differently from a board mismatch and worse. A `max_moves`
    disagreement produces identical play until the shorter limit fires, so it
    surfaces as a DivergenceError about termination after 35 signed turns. A
    `scoring` disagreement never diverges the engines at all: both peers play
    the same match and report different results, which no downstream check
    can catch.

    Absent is not disagreement, as with the axis fields.

    Raises:
        BoardMismatchError: a stated rule differs from ours.
    """
    ours = {"max_moves": config.max_moves, "scoring": scoring_block(config)}
    for field, mine in ours.items():
        theirs = observed.get(field)
        if theirs is None:
            continue
        if field == "scoring":
            _check_scoring(index, theirs, mine)
        elif theirs != mine:
            raise BoardMismatchError(
                f"peer {index} reports {field}={theirs!r}, this engine uses "
                f"{mine!r}. The match would diverge only when the shorter "
                "limit fires, blaming termination for a contract mismatch."
            )


def _check_scoring(index: int, theirs: dict, mine: dict) -> None:
    """Compare the payoff table entry by entry, naming the first difference."""
    for payoff, value in mine.items():
        stated = theirs.get(payoff)
        if stated is not None and stated != value:
            raise BoardMismatchError(
                f"peer {index} reports scoring.{payoff}={stated!r}, this "
                f"engine uses {value!r}. Both peers would play the same match "
                "and report different results."
            )
