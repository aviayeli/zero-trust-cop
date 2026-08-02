"""Play one full P2P match between two LOCAL MCP peers over streamable HTTP.

Removes the external dependency that blocked Step 7b: rather than waiting for
the opposing group, both peers are run locally against each other over a real
transport, with commit-reveal and Ed25519 signatures in force.

Mirrored local truth (D2): each submission is broadcast to BOTH peers, whose
independent engines are compared every turn.
"""

import argparse
import contextlib
import json
from random import Random

import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from engine.board import Board
from engine.config import load_config
from mcp_server.http_peer import HttpPeer
from mcp_server.identity import load_signing_key
from mcp_server.keygen import ensure_keys
from mcp_server.peer_client import PeerClient
from mcp_server.peer_policy import build_peer_policy
from scripts.match_log import write_artifacts
from scripts.match_loop import play_match
from scripts.peer_processes import PEER_ROLES, running_peers

_ENGINE_ROLE = {"police": "cop", "thief": "thief"}


def peer_url(binding) -> str:
    """Streamable-HTTP endpoint for one peer."""
    return f"http://{binding.host}:{binding.my_port}/mcp"


def build_clients(config, seed, config_root=None):
    """Build both peers' signing clients from their private keys and tables."""
    master = Random(seed)
    return {
        role: PeerClient(
            role,
            build_peer_policy(role, _ENGINE_ROLE[role], config, config_root),
            load_signing_key(role, config_root),
            Random(master.random()),
        )
        for role in PEER_ROLES
    }


@contextlib.asynccontextmanager
async def connected_peers(bindings):
    """Open a live session to every peer, closing them all on the way out."""
    async with contextlib.AsyncExitStack() as stack:
        connections = []
        for role in PEER_ROLES:
            read, write, _ = await stack.enter_async_context(
                streamable_http_client(peer_url(bindings[role]))
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            connections.append(HttpPeer(session))
        yield connections


async def run_match(bindings, config, seed, config_root=None):
    """Drive a whole match over the wire and return its per-turn history."""
    clients = build_clients(config, seed, config_root)
    async with connected_peers(bindings) as connections:
        return await play_match(clients, connections, Board(config), config)


def _group_id(config_root=None):
    """The group directory logs land in, from the published declaration."""
    root = config_root or "config"
    with open(f"{root}/declaration.json") as declared:
        return json.load(declared)["group_name"]


def _report(seed, history):
    """Print the match summary, including the seed that reproduces it."""
    final = history[-1]["result"]
    print(f"seed={seed}")
    print(f"turns={len(history)}")
    print(f"terminal_reason={final['terminal_reason']}")
    print(f"captured={final['captured']}")
    print(f"cop_position={tuple(final['cop_position'])}")
    print(f"thief_position={tuple(final['thief_position'])}")
    print("peers_agreed=True")


def main(argv=None):
    """Generate any missing keys, run both peers, and play one match."""
    parser = argparse.ArgumentParser(description="Local P2P MCP match.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--config-root", default=None)
    parser.add_argument("--game-id", default=None,
                        help="artifact game id; omit to skip writing artifacts")
    parser.add_argument("--game-number", type=int, default=1)
    parser.add_argument("--logs-dir", default="logs")
    args = parser.parse_args(argv)

    created = ensure_keys(args.config_root)
    if created:
        print(f"generated_keys={','.join(created)}")

    config = load_config(
        f"{args.config_root or 'config'}/police/game.json"
    )
    with running_peers(args.config_root) as bindings:
        history = anyio.run(run_match, bindings, config, args.seed, args.config_root)

    _report(args.seed, history)

    if args.game_id:
        paths = write_artifacts(
            args.logs_dir, args.game_id, args.game_number, history,
            group_id=_group_id(args.config_root), config_root=args.config_root,
        )
        for kind, path in sorted(paths.items()):
            print(f"{kind}={path}")
    return history


if __name__ == "__main__":
    main()
