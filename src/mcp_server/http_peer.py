"""Present a REMOTE peer's tools with the same signature as an in-process app.

``create_app`` returns tool callables; this returns the same shape over
streamable HTTP. The match loop therefore needs no knowledge of transport,
and the in-process tests and the real wire exercise identical logic.
"""

import json


class HttpPeer:
    """Adapter over an initialised MCP ClientSession."""

    def __init__(self, session):
        """Store an already-initialised client session."""
        self._session = session

    async def _call(self, name: str, arguments: dict) -> dict:
        """Invoke a remote tool and decode its JSON payload."""
        result = await self._session.call_tool(name, arguments)
        return json.loads(result.content[0].text)

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
