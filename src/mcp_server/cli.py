"""Command line for a peer server.

Split from ``server.py`` when the composition root reached the 150-line limit.
The seam is real: ``create_app`` decides what a peer IS, this decides how an
operator starts one. ``server.py`` re-exports both names so the documented
entry point, ``python -m mcp_server.server --role police``, keeps working.
"""

from __future__ import annotations

import argparse

from mcp_server import dialects
from mcp_server.server import PEER_ROLES, create_app


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
        "--dialect", default=None, choices=dialects.DIALECTS,
        help="extra wire dialect to serve; OFF by default because it accepts "
             "unauthenticated submissions (PRD_09 FR5)",
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
    app = create_app(args.role, config_root=args.config_root,
                     dialect=args.dialect)
    app.mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
