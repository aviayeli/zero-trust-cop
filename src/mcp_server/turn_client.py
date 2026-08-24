"""The outbound half of reference-v3 (PRD_10 FR1, FR7).

Two tools carry a whole sub-game: ``receive_turn`` once per half-turn and
``submit_audit`` once at the end. The push dialect's ``receive_commit`` and
``receive_reveal`` are NOT on this wire -- ali-ahm1's server accepts them and
their game loop never reads them, so a client calling one is pushing into a
void that answers 200.

Every argument rides under ONE envelope key. The kit's client wraps its
arguments that way, so a tool declaring flat parameters fails Pydantic
validation on the CALLER's side before the receiver's code runs; the arity is
part of the contract, not an implementation detail.

``seal`` is where the nonce is minted and kept. It is the only evidence that
our disclosed record matches the digest we pushed, it travels once -- at the
end, inside the audit -- and a nonce sealed but not buffered destroys OUR own
defence rather than the opponent's.
"""

from __future__ import annotations

from secrets import token_hex

from mcp_server import interop

# Nonce length in bytes (128 bits), matching mcp_server.crypto. The move set
# has five elements, so a predictable nonce lets an opponent brute-force our
# commitment before the audit discloses it.
_NONCE_BYTES = 16


class TurnClient:
    """Pushes our half-turns to the opponent and closes with the audit.

    ``call`` is an async callable ``(tool_name, **kwargs) -> dict``, so the
    transport stays injectable and the argument sets are testable without a
    network.
    """

    def __init__(self, call, sender: str):
        self._call = call
        self._sender = sender
        self._records: list = []

    @property
    def records(self) -> list:
        """The sealed chain owed to the audit, oldest first."""
        return list(self._records)

    def seal(self, payload: dict) -> tuple:
        """Mint a nonce, digest the payload, buffer both. Returns (commit, nonce).

        Pure and synchronous: sealing is a local act, and keeping it out of
        the awaited path means a network failure can never lose the record of
        a move we have already committed to.
        """
        nonce = token_hex(_NONCE_BYTES)
        commit = interop.commit(payload, nonce)
        self._records.append(
            {"payload": payload, "nonce": nonce, "commit": commit}
        )
        return commit, nonce

    async def turn(self, message: dict) -> dict:
        """One TurnMessage, one half-turn."""
        return await self._call("receive_turn", message=message)

    async def audit(self, result_claim: dict) -> dict:
        """Disclose the whole sealed chain, then clear the buffer.

        ``result_claim`` is what WE believe the sub-game ended as. It is a
        claim, not a verdict: the opponent's re-hash of these records settles
        the sub-game, never the claim.

        Raises:
            ValueError: nothing was sealed. An empty audit asserts a sub-game
                we never played, and reads to the opponent as a chain with no
                steps rather than as our own mistake.
        """
        if not self._records:
            raise ValueError(
                "refusing to send an audit with no records buffered: "
                "nothing was sealed this sub-game"
            )
        records, self._records = self._records, []
        return await self._call("submit_audit", payload={
            "sender": self._sender,
            "records": records,
            "result_claim": result_claim,
        })
