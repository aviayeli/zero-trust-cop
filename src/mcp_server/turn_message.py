"""One outbound reference-v3 ``TurnMessage``, and the record it seals (FR1).

A half-turn on this wire is ONE message. It carries a digest and never the
move: ``commit`` seals ``sealed_payload``'s record, and that record is
disclosed only at ``submit_audit``, once the sub-game is over. Everything the
opponent may act on this step -- the hint, the smell trail, a capture claim,
an honest answer to theirs -- rides in the clear beside it.

The four optional fields are OMITTED unless this turn carries one. Explicit
nulls are equally conformant (the kit's accept case spells them out), but a
log where every turn claims ``capture_claim: null`` hides the one turn that
actually claims.

``sealed_payload`` reproduces the kit's published move-record vector exactly
-- same keys, same ``state`` spelling -- because the opponent re-hashes it
with its own serialiser and any drift is scored as tampering for both sides.
"""

from __future__ import annotations

import datetime

from mcp_server.wire_v3 import TURN_OPTIONAL


def now() -> str:
    """A non-empty ISO-8601 UTC stamp. Decorative field, load-bearing refusal."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def state_string(config, position, barriers) -> str:
    """``grid=7x7;self=[4, 3];barriers=[]`` -- the kit's own vector spelling.

    Built by hand rather than by ``json.dumps`` because the format is not
    JSON: it is a semicolon-joined label whose list segments happen to look
    like Python repr, spaces after the commas included.
    """
    cells = ", ".join(f"[{row}, {col}]" for row, col in sorted(barriers))
    return (
        f"grid={config.grid_size}x{config.grid_size};"
        f"self=[{position[0]}, {position[1]}];"
        f"barriers=[{cells}]"
    )


def sealed_payload(config, step: int, position, move: str, intent: str,
                   hint: str, barriers) -> dict:
    """The record this step's ``commit`` seals.

    ``position`` is in here on purpose: it is what makes a dishonest
    ``claim_response`` detectable at audit. A thief that answers "not caught"
    on a cell its own sealed chain places it on has forged its own evidence.
    """
    return {
        "step": step,
        "state": state_string(config, position, barriers),
        "position": [position[0], position[1]],
        "move": move,
        "intent": intent,
        "hint": hint,
    }


def build_turn(step: int, sender: str, hint: str, smell_grid: dict,
               commit: str, timestamp: str | None = None, **optional) -> dict:
    """Assemble one conformant TurnMessage.

    Raises:
        ValueError: an optional field this wire does not name. Refused rather
            than passed through: an unknown key IS tolerated by a conformant
            receiver, so a typo would ride silently and be ignored forever.
    """
    unknown = sorted(set(optional) - set(TURN_OPTIONAL))
    if unknown:
        raise ValueError(
            f"not fields of a TurnMessage: {unknown}; this wire names "
            f"{list(TURN_OPTIONAL)}"
        )
    message = {
        "step": step,
        "sender": sender,
        "hint": hint,
        "smell_grid": dict(smell_grid),
        "commit": commit,
        "timestamp": timestamp or now(),
    }
    for field in TURN_OPTIONAL:
        if optional.get(field) is not None:
            message[field] = optional[field]
    return message
