"""Play one league match against ANOTHER GROUP's peer over its tunnel.

The local runner spawns both peers and plays them against each other, which
proves our two halves agree and nothing about interop. This one starts only
OUR role and dials the opponent at the ``opponent_url`` their operators
published — the field that was loaded from config since the first phase and
read by nothing, so a league match could not actually be played.

Two peers are still connected and cross-examined every turn (D2): our own,
and theirs. What we no longer do is generate their moves.
"""

import argparse
import contextlib
from random import Random

import anyio

from engine.barriers import populated_board
from engine.config import load_config
from mcp_server.identity import load_signing_key
from mcp_server.keygen import ensure_keys
from mcp_server.peer_client import PeerClient
from mcp_server.peer_policy import build_peer_policy
from mcp_server.transport import load_network_settings
from scripts.match_log import write_artifacts
from scripts.match_report import group_id, report_by_email
from scripts.peer_processes import running_peers
from scripts.remote_match import ENGINE_ROLE, play_remote_match
from scripts.remote_peers import connected_opponent, remote_endpoints


async def run_remote(role, config, seed, config_root=None):
    """Drive a whole remote match and return its per-turn history."""
    binding = load_network_settings(role, config_root)
    client = PeerClient(
        role,
        build_peer_policy(role, ENGINE_ROLE[role], config, config_root),
        load_signing_key(role, config_root),
        Random(seed),
    )
    local_url, remote_url = remote_endpoints(role, config_root)
    async with connected_opponent(
        local_url, remote_url, config, config.watchdog_timeout_sec
    ) as (local, remote):
        return await play_remote_match(
            client, local, remote, populated_board(config), config,
            binding.poll_interval_sec,
        )


def _report(role, history, remote_url):
    """Print the match summary, naming the peer we actually played."""
    final = history[-1]["result"]
    print(f"role={role}")
    print(f"opponent={remote_url}")
    print(f"turns={len(history)}")
    print(f"terminal_reason={final['terminal_reason']}")
    print(f"captured={final['captured']}")
    print(f"cop_position={tuple(final['cop_position'])}")
    print(f"thief_position={tuple(final['thief_position'])}")


def _parse(argv):
    parser = argparse.ArgumentParser(description="Remote P2P MCP league match.")
    parser.add_argument("--role", required=True, choices=("police", "thief"))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--config-root", default=None)
    parser.add_argument("--write-artifacts", action="store_true",
                        help="write the four submission artifacts")
    parser.add_argument("--opponent-id", default=None,
                        help="opposing group id; the match ids derive from it "
                             "and ours, SORTED, so both peers name the "
                             "artifacts alike. Defaults to the other party in "
                             "the contract's agreed_between pair.")
    parser.add_argument("--game-number", type=int, default=1)
    parser.add_argument("--logs-dir", default="logs")
    parser.add_argument(
        "--use-running-peer", action="store_true",
        help="do not spawn our peer; one is already listening (e.g. behind ngrok)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Start our own peer if needed, then play one match against the opponent."""
    args = _parse(argv)
    root = args.config_root or "config"
    config = load_config(f"{root}/{args.role}/game.json")

    created = ensure_keys(args.config_root)
    if created:
        print(f"generated_keys={','.join(created)}")

    _local, remote_url = remote_endpoints(args.role, args.config_root)
    started = (
        contextlib.nullcontext()
        if args.use_running_peer
        else running_peers(args.config_root, roles=(args.role,))
    )
    with started:
        history = anyio.run(
            run_remote, args.role, config, args.seed, args.config_root
        )

    _report(args.role, history, remote_url)

    if args.write_artifacts:
        paths = write_artifacts(
            args.logs_dir, args.game_number, history,
            group_id=group_id(args.config_root), config_root=args.config_root,
            opponent_id=args.opponent_id, our_role=args.role,
        )
        for kind, path in sorted(paths.items()):
            print(f"{kind}={path}")
        report_by_email(paths["result"], args.config_root, args.logs_dir)
    return history


if __name__ == "__main__":
    main()
