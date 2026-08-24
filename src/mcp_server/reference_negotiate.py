"""The ``negotiate`` gate: the only place a mispairing can be caught.

Split from ``reference_tools`` when that module reached the 150-line limit.
The seam is real rather than arithmetic: this tool opens the sub-game and is
the sole authority on whether play may start, while the other three carry
messages once it has. It is also the only one that reasons about the OTHER
peer's identity.
"""

from __future__ import annotations

from mcp_server import interop, wire_v3, wire_v3_session

def _terms_disagreement(ours: dict, theirs: dict) -> str | None:
    """The first term whose VALUE differs, named. A bare "mismatch" sends both
    sides diffing fourteen values that already agree."""
    for term in sorted(set(ours) | set(theirs)):
        if ours.get(term) != theirs.get(term):
            return (
                f"terms disagree on {term}: ours {ours.get(term)!r}, "
                f"theirs {theirs.get(term)!r}"
            )
    return None


def _uid_for(our_terms, identity, message) -> str | None:
    """The match uid, derived from the flat terms and the two group ids.

    Their id comes from the envelope; without it there is no pair to derive
    against, so the check simply does not run.
    """
    ours = identity.get("group_name")
    theirs = message.get("group_id") or (message.get("identity") or {}).get("group_id")
    if not ours or not theirs:
        return None
    return interop.game_uid(our_terms, ours, theirs)


def register(mcp, our_terms, identity_source, nonce_source, our_role):
    """Register ``negotiate`` and return it."""

    @mcp.tool()
    async def negotiate(message: dict) -> dict:
        """The pre-game gate. Either side may open it.

        ONE envelope argument, like every other tool on this wire: the kit's
        client wraps its arguments under a single key, and flat parameters
        fail Pydantic validation on the caller's side before we are reached.

        We verify THEIR signature over THEIR terms with THEIR nonce, then
        require their terms to value-equal ours, then answer with our own
        signed copy. ``sub_game_number`` and ``role`` ride BESIDE ``terms``,
        never inside it: the terms are a flat signed set and an extra key
        breaks the signature.
        """
        verdict = wire_v3_session.validate_negotiate(message)
        if verdict != wire_v3.ACCEPT:
            return {"status": "refused", "reason": verdict}
        terms, nonce = message["terms"], message["nonce"]

        if interop.terms_signature(terms, nonce) != message["signature"]:
            return {
                "status": "refused",
                "reason": "signature does not verify over the terms sent; "
                          "expected SHA256(canonical_json(terms)|nonce), a SINGLE pipe",
            }
        disagreement = _terms_disagreement(our_terms, terms)
        if disagreement:
            return {"status": "refused", "reason": disagreement}

        identity = identity_source()
        our_uid = _uid_for(our_terms, identity, message)
        mispairing = wire_v3_session.pairing_refusal(message, our_role, our_uid)
        if mispairing:
            return {"status": "refused", "reason": mispairing}

        our_nonce = nonce_source()
        return {
            "status": "accepted",
            "terms": our_terms,
            "nonce": our_nonce,
            "signature": interop.terms_signature(our_terms, our_nonce),
            "identity": identity,
            "sub_game_number": message.get("sub_game_number"),
            "role": message.get("role"),
            "game_uid": our_uid,
            "step_semantics": wire_v3.STEP_SEMANTICS,
        }

    return negotiate
