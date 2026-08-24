"""The outbound half of the push dialect (PRD_09 FR2-FR3).

Their tool signatures are narrower than ours, so this client DROPS fields:
``receive_commit`` takes no ``signature`` and ``receive_reveal`` takes no
``nonce`` and no ``state``. Passing an extra keyword would be a TypeError on
their side, so nothing here sends a field their signature does not name.

The dropped nonce is the one that matters. It is the only evidence that our
reveal matched our commitment, and on this wire it travels once, at sub-game
end, through ``receive_final_audit``. A nonce dropped and not buffered
destroys our own defence rather than theirs -- so every commit buffers it,
and the tests assert the buffer by count.

Each buffered entry carries the PAYLOAD its digest sealed, not just the
nonce. A bare nonce leaves the opponent no preimage to rebuild, which is
exactly the gap we have asked them to close (TODO 9.5); sending payloads
costs nothing and means our own chain is auditable even if theirs is not.
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
            {"step": step, "nonce": nonce, "payload": payload}
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

    async def final_audit(self) -> dict:
        """Disclose the whole sub-game's nonces, then clear the buffer.

        Raises:
            ValueError: nothing was buffered. An empty audit would assert a
                sub-game we never played, and reads to the opponent as a
                chain with no steps rather than as our mistake.
        """
        if not self._buffered:
            raise ValueError(
                "refusing to send a final audit with no nonces buffered: "
                "nothing was committed this sub-game"
            )
        entries = list(self._buffered)
        self._buffered = []
        return await self._call(
            "receive_final_audit", role=self._role, nonces=entries
        )
