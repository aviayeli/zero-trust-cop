"""Play a live series against a push-dialect opponent (PRD_09).

Runs OUR peer in-process and drives ``push_runner.play_series`` against the
opponent's endpoint. In-process is not a convenience: their ``receive_commit``
lands in this app's ``PushStore``, so a runner in another process would
complete the handshake and then wait forever for an inbox it cannot see.

    PYTHONPATH=src .venv/bin/python -m scripts.run_push_match \\
        --seed 20260801 --sub-games 6 --first-role police \\
        --opponent-url https://their-tunnel.ngrok-free.dev/mcp

BOTH our peers are served for the whole series. The sides swap every
sub-game, so their pushes land in one of our stores in one sub-game and the
other in the next -- a run that served only the role it starts as would stall
the moment the schedule turned over.

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
    """Serve both our peers, then play the series through them."""
    apps = {
        role: create_app(role, config_root=args.config_root, dialect="push")
        for role in PEER_ROLES
    }
    servers = [asyncio.create_task(app.mcp.run_streamable_http_async())
               for app in apps.values()]
    await asyncio.sleep(_POLL_SECONDS)
    config = apps[args.first_role].config

    async def wait():
        await asyncio.sleep(apps[args.first_role].binding.poll_interval_sec)

    try:
        async with opponent(args.opponent_url, config) as call:
            return await play_series(
                apps, call, sub_games=args.sub_games, seed=args.seed,
                wait=wait, first_role=args.first_role,
            )
    finally:
        for server in servers:
            server.cancel()
        for server in servers:
            with contextlib.suppress(asyncio.CancelledError):
                await server


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Live push-dialect series.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--opponent-url", required=True,
                        help="their /mcp endpoint; one endpoint serves both "
                             "their roles")
    parser.add_argument("--first-role", default="police", choices=PEER_ROLES,
                        help="the side WE play in sub-game 1; it alternates "
                             "from there")
    parser.add_argument("--sub-games", type=int, default=6)
    parser.add_argument("--config-root", default=None)
    return parser.parse_args(argv)


def main(argv=None):
    summaries = asyncio.run(run(parse_args(argv)))
    for summary in summaries:
        print(f"sub_game={summary['sub_game']} role={summary['role']} "
              f"steps={summary['steps']} "
              f"terminal_reason={summary['terminal_reason']}")
        verdict = summary.get("their_audit_response") or {}
        print(f"  their_audit={verdict.get('status', 'no answer')}")
    return summaries


if __name__ == "__main__":
    main()
