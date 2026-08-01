"""Registration of a peer's MCP tool surface.

Split out of ``server.py`` BEFORE it reached the 150-line limit, so the
composition root has room to grow as the peer gains a policy.

A move reaches the engine only through commit-then-reveal. The plaintext
``make_move`` tool this replaced accepted an unsigned direction from any
caller under any role, with nothing binding it to a prior commitment (D3).
"""

from types import SimpleNamespace

from mcp_server import observations


def register_tools(mcp, gate, match_state, config, own_role):
    """Register the peer's four tools and return them as callables.

    NOTE: these parameter names are the P2P wire contract — FastMCP derives
    each tool's public input schema from its signature, so a rename is a
    protocol change. Shadowing the caller's `role` is safe: the peer's own
    identity is read from the captured `own_role`, never from the argument.
    """

    @mcp.tool()
    async def get_observation(role: str) -> dict:
        if role != own_role:
            return observations.build_move_error("invalid_role")
        return observations.build_observation(match_state, config, own_role)

    @mcp.tool()
    async def submit_commitment(
        role: str, turn: int, h_commit: str, signature: str
    ) -> dict:
        return gate.submit_commitment(role, turn, h_commit, signature)

    @mcp.tool()
    async def reveal_move(
        role: str,
        turn: int,
        state: str,
        move: str,
        intent: str,
        nonce: str,
        signature: str,
    ) -> dict:
        return await gate.reveal_move(
            role, turn, state, move, intent, nonce, signature
        )

    @mcp.tool()
    async def get_match_status() -> dict:
        return observations.build_status(match_state)

    return SimpleNamespace(
        get_observation=get_observation,
        submit_commitment=submit_commitment,
        reveal_move=reveal_move,
        get_match_status=get_match_status,
    )
