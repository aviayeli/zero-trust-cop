"""Judging what comes back from a handshake (PRD_10 10.13).

Split from ``negotiate_client`` at the send/judge seam: that module builds and
sends the envelope, this decides whether the reply lets us play.

Two spellings of yes are live -- ours is ``status: "accepted"``, every
opponent we have met answers ``accepted: true`` -- and only a positive verdict
in either counts. Silence is not acceptance and neither is an explicit no.
"""

from __future__ import annotations

from mcp_server import interop, wire_v3_session

_REPLY_REQUIRED = ("terms", "nonce", "signature")


def _require_acceptance(reply) -> None:
    """Raise unless this reply says yes, in either side's spelling.

    Ours is ``status: "accepted"``; theirs is ``accepted: true``. Refusing
    their spelling would stall a live series over a word.
    """
    if not isinstance(reply, dict):
        raise RuntimeError(f"negotiate returned {type(reply).__name__}, not a reply")

    status, accepted = reply.get("status"), reply.get("accepted")
    if status is not None:
        if status != "accepted":
            raise RuntimeError(
                f"opponent refused the handshake: "
                f"{reply.get('reason', status)}"
            )
        return
    if accepted is True:
        return
    if accepted is not None:
        raise RuntimeError(
            f"opponent refused the handshake: {reply.get('reason', accepted)}"
        )
    raise RuntimeError(
        f"negotiate answered with neither 'status' nor 'accepted': {sorted(reply)}. "
        "That is not a handshake, whatever the HTTP code was."
    )


def _check(reply: dict, our_terms: dict, our_role: str,
           our_sub_game: int | None = None) -> bool:
    """Run every check this reply carries the material for.

    Returns whether they COUNTER-SIGNED, i.e. whether the terms-and-signature
    half ran at all. The PAIRING half now also compares ``sub_game_number``:
    SPEC 7.2 refuses when the two differ, and we were echoing theirs and
    playing on -- which is how one game ended up carrying two indices in two
    reports under one ``game_uid``. The pairing half is checked separately and needs only
    ``role``, which is why it is the one check that survives a bare
    acceptance -- and it is the check that matters most, since a mispairing
    is played through coherently by both engines.
    """
    # ROLE and uid contradictions still abort -- they mean we are playing the
    # wrong peer. A sub_game_number disagreement does NOT: SPEC 7.2 says
    # refuse, but rstabcde number by their own attempt counter, so refusing
    # would abort a series that is otherwise perfectly playable and cost the
    # artifact rather than protect it. We RECORD it instead, so the
    # disagreement is in the file a grader reads rather than silently absent.
    mispairing = wire_v3_session.pairing_refusal(reply, our_role, None)
    if mispairing:
        raise RuntimeError(mispairing)

    numbering = wire_v3_session.pairing_refusal(
        {"sub_game_number": reply.get("sub_game_number")}, our_role, None,
        our_sub_game,
    )
    if numbering:
        print(f"  NOTE {numbering}", flush=True)

    if any(key not in reply for key in _REPLY_REQUIRED):
        return False

    if interop.terms_signature(reply["terms"], reply["nonce"]) != reply["signature"]:
        raise RuntimeError(
            "their signature does not verify over the terms they sent; "
            "expected SHA256(canonical_json(terms)|nonce), a SINGLE pipe"
        )

    disagreement = _first_difference(our_terms, reply["terms"])
    if disagreement:
        raise RuntimeError(disagreement)
    return True


def _first_difference(ours: dict, theirs: dict) -> str | None:
    """The first term whose VALUE differs, named. A bare 'mismatch' sends both
    sides diffing fourteen values that already agree."""
    for term in sorted(set(ours) | set(theirs)):
        if ours.get(term) != theirs.get(term):
            return (
                f"terms disagree on {term}: ours {ours.get(term)!r}, "
                f"theirs {theirs.get(term)!r}"
            )
    return None
