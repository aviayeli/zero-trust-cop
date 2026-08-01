"""FastMCP server wiring for zero-trust P2P cop-thief game.

Each peer (police or thief) runs its own independent FastMCP server instance,
with its own config directory and local-truth GameEpisode/MatchState.
Composition root: loads peer-specific config, constructs GameEpisode + MatchState,
registers three thin @tool wrappers delegating to match_state and observations.
"""

import argparse
import os
from types import SimpleNamespace

from mcp.server.fastmcp import FastMCP

from engine.config import load_config
from engine.game_loop import GameEpisode
from mcp_server.commitments import CommitmentBook
from mcp_server.match_state import MatchState
from mcp_server.peer_keys import load_public_keys
from mcp_server.submissions import SubmissionGate
from mcp_server import observations


PEER_ROLES = ("police", "thief")
_ENGINE_ROLE = {"police": "cop", "thief": "thief"}
_DEFAULT_CONFIG_ROOT = "config"
_CONFIG_FILENAME = "game.json"


def peer_config_path(role, config_root=None):
    """Build peer-specific config path: config_root/role/game.json."""
    if config_root is None:
        config_root = os.environ.get("ZTC_CONFIG_ROOT", _DEFAULT_CONFIG_ROOT)
    return os.path.join(config_root, role, _CONFIG_FILENAME)


def create_app(role, config=None, config_root=None):
    """Build a wired FastMCP app for a peer role.

    Args:
        role: "police" or "thief" peer identity.
        config: Optional GameConfig (for testing). If None, loads from config file.
        config_root: Optional config directory override (default: ZTC_CONFIG_ROOT env or "config").

    Returns:
        SimpleNamespace with mcp, match_state, config, role, own_role, config_path,
        and tool callables (get_observation, make_move, get_match_status).
    """
    if role not in PEER_ROLES:
        raise ValueError(f"role must be one of {PEER_ROLES}")

    config_path = peer_config_path(role, config_root)
    if config is None:
        config = load_config(config_path)

    own_role = _ENGINE_ROLE[role]
    episode = GameEpisode(config)
    match_state = MatchState(episode, config.response_timeout_sec)
    book = CommitmentBook()
    gate = SubmissionGate(
        match_state, book, load_public_keys(role, config_root), dict(_ENGINE_ROLE)
    )
    mcp = FastMCP(f"zero-trust-cop-{role}")

    # NOTE: these parameters must stay named `role` — FastMCP derives the public
    # tool input schema from the signature, so a rename changes the P2P wire
    # contract. Shadowing the outer `role` is safe: the peer identity is read
    # from the captured `own_role`, never from the outer name.
    @mcp.tool()
    async def get_observation(role: str) -> dict:
        if role != own_role:
            return observations.build_move_error("invalid_role")
        return observations.build_observation(match_state, config, own_role)

    # A move reaches the engine ONLY through commit-then-reveal. The former
    # plaintext make_move tool accepted an unsigned direction from any caller,
    # under any role, with nothing binding it to a prior commitment (D3).
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
        mcp=mcp,
        match_state=match_state,
        book=book,
        gate=gate,
        config=config,
        role=role,
        own_role=own_role,
        config_path=config_path,
        get_observation=get_observation,
        submit_commitment=submit_commitment,
        reveal_move=reveal_move,
        get_match_status=get_match_status,
    )


def parse_args(argv=None):
    """Parse CLI arguments: --role (required, choices: police/thief), --config-root (optional)."""
    parser = argparse.ArgumentParser(description="Zero-trust cop-thief MCP server")
    parser.add_argument(
        "--role",
        required=True,
        choices=PEER_ROLES,
        help="Peer role: police or thief",
    )
    parser.add_argument(
        "--config-root",
        default=None,
        help="Config directory root (default: ZTC_CONFIG_ROOT env or 'config')",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Run the MCP server for a peer."""
    args = parse_args(argv)
    app = create_app(args.role, config_root=args.config_root)
    app.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
