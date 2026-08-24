"""The league's ``reference-v3`` tool surface, served beside our own dialect.

Four tools (SPEC §7.5): ``negotiate`` and ``receive_turn`` and ``submit_audit``
are REQUIRED, ``receive_control`` is OPTIONAL and answering at all is
conformant. They are registered on the SAME FastMCP app as our native
commit/reveal tools, so one peer answers both dialects and an opponent on
either can reach us.

What these tools do NOT do is play the game for us. reference-v3 is symmetric
push: each side calls the other's ``receive_turn`` and polls its own inbox,
and a turn carries a COMMIT that is never revealed until ``submit_audit`` at
the end of the sub-game. Our engine resolves a turn only once both sides have
REVEALED, so an inbound reference-v3 turn is validated, recorded and made
available -- it cannot by itself advance our resolver. Driving a full sub-game
on this surface needs a match loop that plays on claims rather than reveals;
that is a separate phase, and pretending otherwise here would give us a peer
that answers to the right names and still cannot finish a game.
"""

from __future__ import annotations

import datetime

from mcp_server import interop, wire_v3


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


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


def register_reference_tools(mcp, inbox, our_terms, identity_source, nonce_source):
    """Register the reference-v3 surface and return the callables.

    ``inbox`` is the list an inbound turn is appended to -- the opponent polls
    its own inbox for ours, and we poll this one for theirs.

    ``identity_source`` is a CALLABLE, resolved when ``negotiate`` runs rather
    than at boot: a peer with no declaration on disk must still answer
    ``tools/list``, because that -- not a tool call -- is the liveness probe.
    Refusing to start would read to an opponent as "not there".
    """

    @mcp.tool()
    async def negotiate(
        terms: dict,
        nonce: str,
        signature: str,
        identity: dict | None = None,
        sub_game_number: int | None = None,
        role: str | None = None,
    ) -> dict:
        """The pre-game gate. Either side may open it.

        We verify THEIR signature over THEIR terms with THEIR nonce, then
        require their terms to value-equal ours, then answer with our own
        signed copy. ``sub_game_number`` and ``role`` ride BESIDE ``terms``,
        never inside it: the terms are a flat signed set and an extra key
        breaks the signature.
        """
        if interop.terms_signature(terms, nonce) != signature:
            return {
                "status": "refused",
                "reason": "signature does not verify over the terms sent; "
                          "expected SHA256(canonical_json(terms)|nonce), a SINGLE pipe",
            }
        disagreement = _terms_disagreement(our_terms, terms)
        if disagreement:
            return {"status": "refused", "reason": disagreement}

        our_nonce = nonce_source()
        return {
            "status": "accepted",
            "terms": our_terms,
            "nonce": our_nonce,
            "signature": interop.terms_signature(our_terms, our_nonce),
            "identity": identity_source(),
            "sub_game_number": sub_game_number,
            "role": role,
            "step_semantics": wire_v3.STEP_SEMANTICS,
        }

    @mcp.tool()
    async def receive_turn(message: dict) -> dict:
        """One TurnMessage per half-turn. Validated BEFORE anything is stored."""
        verdict = wire_v3.validate_turn_message(message)
        if verdict != wire_v3.ACCEPT:
            return {"status": "refused", "reason": verdict}
        inbox.append(dict(message))
        return {"status": "accepted", "step": message["step"],
                "received_at": _now()}

    @mcp.tool()
    async def submit_audit(payload: dict) -> dict:
        """One AuditPayload per sub-game: re-hash their chain with OUR serializer.

        This is the whole point of the audit -- their ``result_claim`` is a
        claim, and our recomputation is the evidence. A canonicalization
        difference surfaces here as a mismatch, which is why §2's
        ``ensure_ascii=False`` is load-bearing.
        """
        verdict = wire_v3.validate_audit_payload(payload)
        if verdict != wire_v3.ACCEPT:
            return {"status": "refused", "reason": verdict}

        mismatches = [
            record["step"]
            for record in payload["records"]
            if interop.commit(record["payload"], record["nonce"]) != record["commit"]
        ]
        return {
            "status": "tampered" if mismatches else "accepted",
            "records_verified": len(payload["records"]) - len(mismatches),
            "mismatches": mismatches,
            "result_claim": payload["result_claim"],
        }

    @mcp.tool()
    async def receive_control(message: dict) -> dict:
        """A status channel touching no game state, never sealed, never scored."""
        verdict = wire_v3.validate_control_message(message)
        if verdict != wire_v3.ACCEPT:
            return {"status": "refused", "reason": verdict}
        return {"status": "ok", "kind": message["kind"], "at": _now()}

    return {
        "negotiate": negotiate,
        "receive_turn": receive_turn,
        "submit_audit": submit_audit,
        "receive_control": receive_control,
    }
