"""Is a match log well-FORMED? (shape and vocabulary, not cryptography.)

Separated from log_checks.py, which asks whether a well-formed log is
cryptographically sound. Keeping them apart lets each grow without either
breaching the 150-line rule, and makes the ordering explicit: shape first,
because every later check indexes fields these guarantee exist.
"""

from mcp_server.directions import is_intent

PEER_ROLES = ("police", "thief")

def check_structure(log, failures) -> bool:
    """Validate the shape every later check assumes. False stops the run."""
    turns = log.get("turns")
    if not isinstance(turns, list) or not turns:
        failures.append("log contains no turns")
        return False
    for index, turn in enumerate(turns):
        submissions = turn.get("submissions") if isinstance(turn, dict) else None
        if not isinstance(submissions, dict):
            failures.append(f"turn {index}: no submissions block")
            continue
        missing = [role for role in PEER_ROLES if role not in submissions]
        if missing:
            failures.append(f"turn {index}: missing submissions for {missing}")
        if not isinstance(turn.get("result"), dict):
            failures.append(f"turn {index}: no result block")
    return not failures


def check_intents(log, failures) -> None:
    """The honesty flag must be exactly 'truth' or 'lie' (payload v3.0.0).

    Separate from the structural gate so an invalid flag reports alongside the
    digest and signature results rather than masking them.
    """
    for index, turn in enumerate(log["turns"]):
        for role, entry in turn["submissions"].items():
            if not is_intent(entry.get("intent")):
                failures.append(
                    f"turn {index} {role}: intent must be 'truth' or 'lie', "
                    f"got {entry.get('intent')!r}"
                )


def check_turn_indices(log, failures) -> None:
    """Turn indices must be contiguous and ascending (V2).

    Signatures bind each entry's OWN turn field, so reordering entries is
    invisible to the signature check.
    """
    for index, turn in enumerate(log["turns"]):
        if turn.get("turn") != index:
            failures.append(f"turn {index}: index recorded as {turn.get('turn')!r}")

