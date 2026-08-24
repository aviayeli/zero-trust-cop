"""FastMCP server wiring for zero-trust P2P cop-thief game.

Each peer (police or thief) runs its own independent FastMCP server instance,
with its own config directory and local-truth GameEpisode/MatchState — the
mirrored-local-truth topology of D2, in which neither peer trusts the other's
engine.

Composition root only: it loads peer config, assembles the episode, buffer,
commitment book, authenticated submission gate and greedy policy, then hands
tool registration to mcp_server.tools.

TWO DIALECTS are served on one app: our native commit/reveal surface
(mcp_server.tools) and the league's reference-v3 surface
(mcp_server.reference_tools), so an opponent on either can reach this peer.
Compare tool LISTS before comparing anything inside them -- two peers can
agree every term and still exchange nothing because their surfaces are
disjoint.
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
from mcp_server import reference_surface
from mcp_server.peer_policy import build_peer_policy
from mcp_server.submissions import SubmissionGate
from mcp_server.transport import load_network_settings
from mcp_server.tools import register_tools


PEER_ROLES = ("police", "thief")
_ENGINE_ROLE = {"police": "cop", "thief": "thief"}
_DEFAULT_CONFIG_ROOT = "config"
_CONFIG_FILENAME = "game.json"


def peer_config_path(role, config_root=None):
    """Build peer-specific config path: config_root/role/game.json."""
    if config_root is None:
        config_root = os.environ.get("ZTC_CONFIG_ROOT", _DEFAULT_CONFIG_ROOT)
    return os.path.join(config_root, role, _CONFIG_FILENAME)


def create_app(role, config=None, config_root=None, clock=None):
    """Build a wired FastMCP app for a peer role.

    Args:
        role: "police" or "thief" peer identity.
        config: Optional GameConfig (for testing). If None, loads from file.
        config_root: Optional config directory override.
        clock: Optional monotonic clock for the commitment timeout (testing).

    Returns:
        SimpleNamespace with mcp, match_state, book, gate, policy, config,
        role, own_role, config_path, and the registered tool callables.

    Raises:
        ValueError: unknown role, mismatched table layout, or an empty table.
        FileNotFoundError: the peer's configured qtable_path is absent.
    """
    if role not in PEER_ROLES:
        raise ValueError(f"role must be one of {PEER_ROLES}")

    config_path = peer_config_path(role, config_root)
    if config is None:
        config = load_config(config_path)

    own_role = _ENGINE_ROLE[role]
    episode = GameEpisode(config)
    match_state = MatchState(episode, config.response_timeout_sec)
    book = CommitmentBook(
        timeout_seconds=config.response_timeout_sec,
        **({"clock": clock} if clock is not None else {}),
    )
    gate = SubmissionGate(
        match_state, book, load_public_keys(role, config_root), dict(_ENGINE_ROLE)
    )
    policy = build_peer_policy(role, own_role, config, config_root)

    binding = load_network_settings(role, config_root)
    mcp = FastMCP(
        f"zero-trust-cop-{role}",
        host=binding.host,
        port=binding.my_port,
        log_level="ERROR",
    )
    tools = register_tools(mcp, gate, match_state, config, own_role)

    # The reference-v3 half. `inbox` is where an inbound TurnMessage lands:
    # the transport is symmetric push, so each side polls its own inbox.
    reference = reference_surface.build(mcp, role, config_path, config_root)

    return SimpleNamespace(
        mcp=mcp,
        inbox=reference.inbox,
        terms=reference.terms,
        **reference.tools,
        match_state=match_state,
        book=book,
        gate=gate,
        policy=policy,
        config=config,
        role=role,
        own_role=own_role,
        config_path=config_path,
        binding=binding,
        **vars(tools),
    )


def parse_args(argv=None):
    """Parse CLI arguments: --role (required), --config-root (optional)."""
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
    parser.add_argument(
        "--transport",
        default="streamable-http",
        choices=("stdio", "streamable-http"),
        help="Wire transport; D1 rules streamable HTTP for local P2P play",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Run the MCP server for a peer."""
    args = parse_args(argv)
    app = create_app(args.role, config_root=args.config_root)
    app.mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
