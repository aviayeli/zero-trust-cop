"""Transport and command line for the pre-game probe (PRD_11).

Split from ``scripts.netcheck`` at the 150-line limit. The seam is real rather
than arithmetic: that module decides what a healthy opponent looks like, and
this one knows how to reach one and what an operator may ask for.

The session is built the way a real series builds it -- same streamable-HTTP
client, same ``watchdog_timeout_sec``, same agreed ``rate_limiter_gatekeeper``
throttle. A probe riding a different transport verifies a path we will not
use, which is how a green check precedes a dead series.

``list_tools`` is a SESSION method, not a tool call, so the peer handle
carries both: ``HttpPeer.call`` for tools and the session's own listing for
the surface check.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
from types import SimpleNamespace

from engine.config import load_config
from mcp_server.reference_surface import identity_block
from mcp_server.server import PEER_ROLES
from mcp_server.terms import terms_from_config
from scripts.netcheck import exit_code, probe

CONTRACT = "game.json"


def _root(config_root):
    return config_root or os.environ.get("ZTC_CONFIG_ROOT", "config")


async def _tool_names(session) -> list:
    """The tool names this peer advertises, flattened out of the MCP reply."""
    listed = await session.list_tools()
    return [tool.name for tool in listed.tools]


@contextlib.asynccontextmanager
async def session_peer(url: str, config):
    """A handle over one opponent endpoint: ``list_tools`` and ``call``."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    from mcp_server.http_peer import HttpPeer
    from scripts.remote_peers import opponent_limiter

    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            peer = HttpPeer(session, config.watchdog_timeout_sec,
                            limiter=opponent_limiter(config))
            yield SimpleNamespace(
                list_tools=lambda: _tool_names(session),
                call=peer.call,
            )


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Check an opponent's reference-v3 endpoint before "
                    "committing a series to it. Read-only: it opens no "
                    "sub-game, pushes no turn and writes no artifact.")
    parser.add_argument("--opponent-url", required=True,
                        help="their /mcp endpoint, e.g. "
                             "https://them.ngrok-free.dev/mcp")
    parser.add_argument("--role", default="police", choices=tuple(PEER_ROLES),
                        help="the side WE would play; it rides in the probe "
                             "handshake so a role collision is caught here "
                             "rather than in sub-game 1")
    parser.add_argument("--config-root", default=None)
    return parser.parse_args(argv)


def render(url: str, report: list) -> str:
    """The operator's whole answer: one line per check, then a verdict."""
    lines = [f"netcheck {url}"]
    for check in report:
        mark = "ok  " if check["ok"] else "FAIL"
        lines.append(f"  [{mark}] {check['check']}: {check['detail']}")
    ran = {check["check"] for check in report}
    for skipped in ("reachable", "surface", "handshake", "terms"):
        if skipped not in ran:
            lines.append(f"  [ -- ] {skipped}: not reached")
    lines.append("READY" if exit_code(report) == 0 else "NOT READY")
    return "\n".join(lines)


def main(argv=None) -> int:
    """Probe one endpoint and return a shell exit code (FR7)."""
    args = parse_args(argv)
    contract = os.path.join(_root(args.config_root), CONTRACT)
    with open(contract, encoding="utf-8") as shared:
        our_terms = terms_from_config(json.load(shared))

    report = asyncio.run(probe(
        lambda: session_peer(args.opponent_url, load_config(contract)),
        our_terms, identity_block(args.role, args.config_root), args.role,
    ))
    print(render(args.opponent_url, report), flush=True)
    return exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
