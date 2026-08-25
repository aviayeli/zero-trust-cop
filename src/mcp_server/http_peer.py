"""Present a REMOTE peer's tools with the same signature as an in-process app.

``create_app`` returns tool callables; this returns the same shape over
streamable HTTP. The match loop therefore needs no knowledge of transport,
and the in-process tests and the real wire exercise identical logic.

Every call is fenced by the published ``watchdog_timeout_sec``. ``call_tool``
has no deadline of its own, so a peer that accepts the connection and then goes
quiet would leave the match awaiting a reply forever. The deadline is a
REQUIRED constructor argument rather than a defaulted one: a default is exactly
how one call site quietly reintroduces the hang.
"""

import asyncio
import json


class TechnicalLossError(RuntimeError):
    """A peer failed to answer inside the watchdog window (rulebook forfeit).

    Raised rather than absorbed: a stalled peer is a match outcome, not a
    transport hiccup to retry, and the caller decides who is awarded the loss.
    """


class HttpPeer:
    """Adapter over an initialised MCP ClientSession."""

    def __init__(self, session, timeout_seconds: float, limiter=None):
        """Store an already-initialised session, its deadline and its throttle.

        ``limiter`` of None sends unthrottled, which is what the in-process
        tests and the loopback simulation want; league play passes the agreed
        `rate_limiter_gatekeeper` policy (``mcp_server/rate_limiter.py``).
        """
        self._session = session
        self.timeout_seconds = timeout_seconds
        self._limiter = limiter

    async def _call(self, name: str, arguments: dict) -> dict:
        """Invoke a remote tool under the watchdog and decode its payload."""
        async def invoke():
            try:
                return await asyncio.wait_for(
                    self._session.call_tool(name, arguments), self.timeout_seconds
                )
            except TimeoutError as expiry:
                raise TechnicalLossError(
                    f"peer did not answer {name!r} within "
                    f"{self.timeout_seconds} seconds"
                ) from expiry

        result = await (invoke() if self._limiter is None else self._limiter.run(invoke))
        return json.loads(result.content[0].text)

    async def call(self, name: str, **arguments) -> dict:
        """Invoke any tool by name, under the same watchdog and limiter.

        The named wrappers below cover our own dialect; a second dialect
        needs the generic form rather than a private call from outside.
        """
        return await self._call(name, arguments)

    async def submit_commitment(self, role, turn, h_commit, signature) -> dict:
        return await self._call(
            "submit_commitment",
            {
                "role": role,
                "turn": turn,
                "h_commit": h_commit,
                "signature": signature,
            },
        )

    async def reveal_move(
        self, role, turn, state, move, intent, nonce, signature
    ) -> dict:
        return await self._call(
            "reveal_move",
            {
                "role": role,
                "turn": turn,
                "state": state,
                "move": move,
                "intent": intent,
                "nonce": nonce,
                "signature": signature,
            },
        )

    async def get_match_status(self) -> dict:
        return await self._call("get_match_status", {})

    async def get_observation(self, role) -> dict:
        return await self._call("get_observation", {"role": role})
