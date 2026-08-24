"""Play a live series against a push-dialect opponent (PRD_09).

Runs OUR peer in-process and drives ``push_runner.play_series`` against the
opponent's endpoint. In-process is not a convenience: their ``receive_commit``
lands in this app's ``PushStore``, so a runner in another process would
complete the handshake and then wait forever for an inbox it cannot see.

    PYTHONPATH=src .venv/bin/python -m scripts.run_push_match \\
        --role police --seed 20260801 --sub-games 1 \\
        --opponent-url https://their-tunnel.ngrok-free.dev/mcp

This speaks the UNAUTHENTICATED dialect: no signature per commit, no nonce
per reveal, detection deferred to the audit. It is opt-in for that reason.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_server.http_peer import HttpPeer
from mcp_server.push_client import PushClient
from mcp_server.server import PEER_ROLES, create_app
from scripts.push_runner import play_series
from scripts.remote_peers import opponent_limiter

_POLL_SECONDS = 0.5


@contextlib.asynccontextmanager
async def opponent(url: str, config):
    """A callable that invokes one of their tools, under our watchdog.

    Rate-limited by the agreed ``rate_limiter_gatekeeper`` block: the other
    end is another group's server, and if they enforce it and we do not, WE
    are the side that gets dropped.
    """
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            peer = HttpPeer(session, config.watchdog_timeout_sec,
                            limiter=opponent_limiter(config))

            yield peer.call


async def run(args) -> list:
    """Serve our peer, then play the series through it."""
    app = create_app(args.role, config_root=args.config_root, dialect="push")
    server = asyncio.create_task(app.mcp.run_streamable_http_async())
    await asyncio.sleep(_POLL_SECONDS)

    async def wait():
        await asyncio.sleep(app.binding.poll_interval_sec)

    try:
        async with opponent(args.opponent_url, app.config) as call:
            return await play_series(
                app, PushClient(call, args.role),
                sub_games=args.sub_games, seed=args.seed, wait=wait,
            )
    finally:
        server.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Live push-dialect series.")
    parser.add_argument("--role", required=True, choices=PEER_ROLES)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--opponent-url", required=True,
                        help="their /mcp endpoint for the role we are NOT")
    parser.add_argument("--sub-games", type=int, default=1)
    parser.add_argument("--config-root", default=None)
    return parser.parse_args(argv)


def main(argv=None):
    summaries = asyncio.run(run(parse_args(argv)))
    for summary in summaries:
        print(f"sub_game={summary['sub_game']} steps={summary['steps']} "
              f"terminal_reason={summary['terminal_reason']}")
        verdict = summary.get("their_audit_response") or {}
        print(f"  their_audit={verdict.get('status', 'no answer')}")
    return summaries


if __name__ == "__main__":
    main()
