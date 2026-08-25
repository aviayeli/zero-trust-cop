"""Serve both our peers on one port, for handshake testing (PRD_11b).

This binds the unified surface and answers. It does NOT play: a series needs
``run_reference_match``, whose loop owns the inbox it polls and sets the active
role per sub-game. Running this during a real match would put a second listener
on our state.

What it IS for: giving an opponent one URL to verify against before a series --
`negotiate`, the tool list, the terms comparison -- which is exactly what
``scripts.netcheck`` checks and exactly what took two days to establish with
bb-ai-12 across two tunnels.

    PYTHONPATH=src .venv/bin/python -m scripts.unified_serve --first-role police
"""

from __future__ import annotations

import argparse
import asyncio

from mcp_server.server import PEER_ROLES
from mcp_server.unified import create_unified_app


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Serve both peers on the configured unified port.")
    parser.add_argument("--first-role", default="police", choices=PEER_ROLES,
                        help="the side we answer as until told otherwise; the "
                             "handshake's pairing check compares against it")
    parser.add_argument("--config-root", default=None)
    parser.add_argument("--port", type=int, default=None,
                        help="override the configured unified_port")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    app = create_unified_app(config_root=args.config_root, port=args.port)
    app.set_active(args.first_role)
    print(f"unified endpoint on :{app.port}/mcp "
          f"serving police+thief, answering as {args.first_role}", flush=True)
    asyncio.run(app.mcp.run_streamable_http_async())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
