"""The outbound half of the push dialect (PRD_09 FR2-FR3).

Their tool signatures are narrower than ours, so this client DROPS fields:
``receive_commit`` takes no ``signature`` and ``receive_reveal`` takes no
``nonce`` and no ``state``. Passing an extra keyword would be a TypeError on
their side, so nothing here sends a field their signature does not name.

The dropped nonce is the one that matters. It is the only evidence that our
reveal matched our commitment, and on this wire it travels once, at sub-game
end, through ``submit_audit``. A nonce dropped and not buffered destroys our
own defence rather than theirs -- so every commit buffers it, and the tests
assert the buffer by count.

The audit step is ``submit_audit(payload={sender, records, result_claim})``,
each record ``{payload, nonce, commit}`` -- ali-ahm1 confirmed this on
2026-08-24, correcting their earlier ``receive_final_audit(role, nonces)``.
The correction is what makes the audit possible at all: the flat form carried
bare nonces, and without the payload a digest has no preimage to rebuild, so
the audit was not late but uncomputable. Every record here therefore carries
its own preimage, and neither side has to reconstruct the other's payload.
"""

from __future__ import annotations


class PushClient:
    """Pushes our half of a sub-game to the opponent's ``receive_*`` tools.

    ``call`` is an async callable ``(tool_name, **kwargs) -> dict``, so the
    transport stays injectable and the argument sets are testable without a
    network.
    """

    def __init__(self, call, role: str):
        self._call = call
        self._role = role
        self._buffered: list = []

    @property
    def buffered(self) -> list:
        """The nonces owed to the final audit, oldest first."""
        return list(self._buffered)

    async def step0(self, declaration: dict, signature: str) -> dict:
        """The one message on this wire that carries a signature."""
        return await self._call(
            "receive_step0", role=self._role,
            declaration=declaration, signature=signature,
        )

    async def commit(self, step: int, h_commit: str, nonce: str,
                     payload: dict) -> dict:
        """Send the digest; keep the nonce and its preimage for the audit."""
        self._buffered.append(
            {"payload": payload, "nonce": nonce, "commit": h_commit}
        )
        return await self._call(
            "receive_commit", role=self._role, step=step, h_commit=h_commit,
        )

    async def reveal(self, step: int, move: str, hint: str,
                     intent: str) -> dict:
        """Send the move WITHOUT its nonce or state -- their signature has
        neither, so the opponent cannot check this against the commitment
        until the audit."""
        return await self._call(
            "receive_reveal", role=self._role, step=step,
            move=move, hint=hint, intent=intent,
        )

    async def ack(self, step: int) -> dict:
        return await self._call("receive_ack", role=self._role, step=step)

    async def capture_claim(self, claimed) -> dict:
        return await self._call(
            "receive_capture_claim", role=self._role, claimed=claimed
        )

    async def final_audit(self, result_claim: dict) -> dict:
        """Disclose the whole sealed chain, then clear the buffer.

        ``result_claim`` is what WE believe the sub-game ended as. It is a
        claim, not a verdict: the opponent's re-hash of these records settles
        the sub-game, never the claim.

        Raises:
            ValueError: nothing was buffered. An empty audit would assert a
                sub-game we never played, and reads to the opponent as a
                chain with no steps rather than as our own mistake.
        """
        if not self._buffered:
            raise ValueError(
                "refusing to send an audit with no records buffered: "
                "nothing was committed this sub-game"
            )
        records = list(self._buffered)
        self._buffered = []
        return await self._call("submit_audit", payload={
            "sender": self._role,
            "records": records,
            "result_claim": result_claim,
        })
