"""The league's ``reference-v3`` tool surface, served beside our own dialect.

Four tools (SPEC §7.5): ``negotiate`` and ``receive_turn`` and ``submit_audit``
are REQUIRED, ``receive_control`` is OPTIONAL and answering at all is
conformant. They are registered on the SAME FastMCP app as our native
commit/reveal tools, so one peer answers both dialects and an opponent on
either can reach us.

These tools RECEIVE; ``scripts.claims_match_loop`` plays (PRD_10). The
transport is symmetric push -- each side calls the other's ``receive_turn``
and polls its own inbox -- and a turn carries a COMMIT that is never revealed
until ``submit_audit`` at the end of the sub-game. There is no move on this
wire, so nothing here can advance our two-piece resolver, and nothing tries
to: the loop that plays on this surface resolves OUR piece alone and settles
capture by claim and honest answer.

That is also why ``submit_audit`` compares against ``inbox``. Every turn we
accepted carried that step's digest, and it arrived before the outcome was
known, so the inbox is the evidence a chain rewritten after the fact fails.
"""

from __future__ import annotations

import datetime

from mcp_server import (audit_check, reference_negotiate, wire_v3,
                        wire_v3_session)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def register_reference_tools(mcp, inbox, audits, our_terms, identity_source,
                            nonce_source, our_role):
    """Register the reference-v3 surface and return the callables.

    ``inbox`` is the list an inbound turn is appended to -- the opponent polls
    its own inbox for ours, and we poll this one for theirs.

    ``audits`` is where their DISCLOSED chains are kept. They used to be
    verified and dropped, which left our log holding their play as one digest
    per step: their moves and positions are disclosed here and nowhere else,
    so discarding the payload meant asserting a verdict nobody could recheck
    -- and made it impossible to catch an opponent walking through a cell our
    board holds as a wall.

    ``identity_source`` is a CALLABLE, resolved when ``negotiate`` runs rather
    than at boot: a peer with no declaration on disk must still answer
    ``tools/list``, because that -- not a tool call -- is the liveness probe.
    Refusing to start would read to an opponent as "not there".
    """

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
        """One AuditPayload per sub-game: judge their chain against OUR evidence.

        Their ``result_claim`` is a claim; our recomputation is the evidence.
        Two things are recomputed: that each record re-hashes to its own
        commit with our serializer (where a canonicalization difference
        surfaces, which is why §2's ``ensure_ascii=False`` is load-bearing),
        and that the commit disclosed is the digest they PUSHED at that step.
        The second is what a chain rewritten after the fact fails.
        """
        verdict = wire_v3_session.validate_audit_payload(payload)
        if verdict != wire_v3.ACCEPT:
            return {"status": "refused", "reason": verdict}

        verdict = dict(
            audit_check.verify_records(payload["records"], inbox),
            result_claim=payload["result_claim"],
        )
        # AFTER validation, so a refused payload never enters the record --
        # and for a TAMPERED one especially, since a verdict of cheating with
        # the evidence thrown away is an accusation we cannot support.
        audits.append({
            "sender": payload["sender"],
            "records": [dict(record) for record in payload["records"]],
            "result_claim": payload["result_claim"],
            "verdict": verdict,
        })
        return verdict

    @mcp.tool()
    async def receive_control(message: dict) -> dict:
        """A status channel touching no game state, never sealed, never scored."""
        verdict = wire_v3_session.validate_control_message(message)
        if verdict != wire_v3.ACCEPT:
            return {"status": "refused", "reason": verdict}
        return {"status": "ok", "kind": message["kind"], "at": _now()}

    negotiate = reference_negotiate.register(
        mcp, our_terms, identity_source, nonce_source, our_role
    )

    return {
        "negotiate": negotiate,
        "receive_turn": receive_turn,
        "submit_audit": submit_audit,
        "receive_control": receive_control,
    }
