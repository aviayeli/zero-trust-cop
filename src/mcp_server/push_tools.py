"""The push dialect's inbound tools (PRD_09 FR1-FR4). OPT-IN -- see FR5.

This surface accepts UNAUTHENTICATED submissions. ``receive_commit`` carries
no signature, so nothing here binds a move to a peer identity, and
``receive_reveal`` carries no nonce, so nothing binds a reveal to its
commitment while the sub-game runs. Our own dialect exists precisely to
prevent both, which is why these tools are registered only when the operator
asks for them by name.

Detection is deferred to ``receive_final_audit`` -- and whether it can happen
at all depends on what the opponent's nonce entries carry. When they carry no
payload there is nothing to re-hash against, and this module says
``unverifiable`` rather than ``accepted``. Reporting a pass we never computed
would be worse than reporting none.
"""

from __future__ import annotations

from mcp_server import push_messages
from mcp_server.push_audit import PushStore, audit_nonces


def register_push_tools(mcp, store: PushStore):
    """Register the six inbound tools. Caller decides whether to call this."""

    def _record(validate, message, apply):
        verdict = validate(message)
        if verdict != push_messages.ACCEPT:
            return {"status": "refused", "reason": verdict}
        return apply(message)

    @mcp.tool()
    async def receive_step0(role: str, declaration: dict, signature: str) -> dict:
        def apply(message):
            store.step0 = dict(message)
            return {"status": "accepted"}

        return _record(push_messages.validate_step0,
                       {"role": role, "declaration": declaration,
                        "signature": signature}, apply)

    @mcp.tool()
    async def receive_commit(role: str, step: int, h_commit: str) -> dict:
        def apply(message):
            store.commits[message["step"]] = message["h_commit"]
            return {"status": "accepted", "step": message["step"]}

        return _record(push_messages.validate_commit,
                       {"role": role, "step": step, "h_commit": h_commit}, apply)

    @mcp.tool()
    async def receive_reveal(
        role: str, step: int, move: str, hint: str, intent: str
    ) -> dict:
        def apply(message):
            store.reveals[message["step"]] = {
                "role": message["role"], "move": message["move"],
                "hint": message["hint"], "intent": message["intent"],
            }
            return {"status": "accepted", "step": message["step"]}

        return _record(push_messages.validate_reveal,
                       {"role": role, "step": step, "move": move,
                        "hint": hint, "intent": intent}, apply)

    @mcp.tool()
    async def receive_ack(role: str, step: int) -> dict:
        def apply(message):
            store.acks.append(message["step"])
            return {"status": "ok", "step": message["step"]}

        return _record(push_messages.validate_ack,
                       {"role": role, "step": step}, apply)

    @mcp.tool()
    async def receive_capture_claim(role: str, claimed) -> dict:
        def apply(message):
            store.claims.append(message["claimed"])
            return {"status": "ok"}

        return _record(push_messages.validate_capture_claim,
                       {"role": role, "claimed": claimed}, apply)

    @mcp.tool()
    async def receive_final_audit(role: str, nonces: list) -> dict:
        def apply(message):
            store.nonces = list(message["nonces"])
            return audit_nonces(store, store.nonces)

        return _record(push_messages.validate_final_audit,
                       {"role": role, "nonces": nonces}, apply)

    return {
        "receive_step0": receive_step0, "receive_commit": receive_commit,
        "receive_reveal": receive_reveal, "receive_ack": receive_ack,
        "receive_capture_claim": receive_capture_claim,
        "receive_final_audit": receive_final_audit,
    }
