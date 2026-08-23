"""Prepare this checkout for a live league match against another group.

Neither step has a local symptom; the loopback simulation passes either way.
The opposing group finds us through ``config/declaration.json``, which ships
naming ``127.0.0.1``, and our server verifies THEIR moves against
``config/police/peers/thief.pub``, which ships holding our OWN thief's key —
so until it holds theirs, everything they sign is refused on turn 0.

Both inputs are validated BEFORE anything is written: a mistyped endpoint or a
truncated key must not be able to replace a working one.
"""

import argparse
import json
import os
from pathlib import Path

from mcp_server.identity import peer_public_key_path
from mcp_server.tunnel import parse_public_url

ENGINE_ROLE = {"police": "cop", "thief": "thief"}
DECLARATION = "declaration.json"
MCP_PATH = "/mcp"
KEY_BYTES = 32


def _root(config_root):
    return config_root or os.environ.get("ZTC_CONFIG_ROOT", "config")


def mcp_endpoint(url: str) -> str:
    """Normalise a tunnel URL to the MCP endpoint a peer actually calls.

    ngrok hands out a bare host, but the declaration must name ``/mcp``, not
    the site root — a peer dialling the root gets a 404 that reads like the
    tunnel being down. One that already says ``/mcp`` is not doubled. Raises
    ValueError on anything unreachable over HTTP.
    """
    validated = parse_public_url(url)
    if not validated:
        raise ValueError("public URL must not be empty")
    if validated.endswith(MCP_PATH):
        return validated
    return validated + MCP_PATH


def set_public_url(url: str, role: str = "police", config_root=None) -> tuple:
    """Advertise our tunnel in the declaration the opposing group reads.

    Returns ``(previous_endpoint, new_endpoint)``.

    Raises:
        ValueError: the URL is not a reachable http(s) endpoint.
    """
    endpoint = mcp_endpoint(url)
    path = Path(_root(config_root)) / DECLARATION
    payload = json.loads(path.read_text(encoding="utf-8"))
    engine = ENGINE_ROLE[role]
    previous = payload["mcp_servers"][engine]
    payload["mcp_servers"][engine] = endpoint
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return previous, endpoint


def _validated_key(source: str) -> str:
    """Read a raw-hex Ed25519 public key, refusing anything unusable.

    Mirrors ``identity.load_peer_public_key`` on purpose: the check belongs
    HERE, before a working key is overwritten — not later, when the server
    first tries to load what we installed.

    Raises:
        ValueError: the file is not 32 bytes of hexadecimal.
    """
    raw = Path(source).read_text(encoding="utf-8").strip()
    try:
        decoded = bytes.fromhex(raw)
    except ValueError as exc:
        raise ValueError(f"{source} is not valid hexadecimal") from exc
    if len(decoded) != KEY_BYTES:
        raise ValueError(
            f"{source} holds {len(decoded)} bytes, not {KEY_BYTES}"
        )
    return raw


def install_opponent_key(
    source: str, own_role: str = "police", peer_role: str = "thief",
    config_root=None,
) -> tuple:
    """Install the opposing group's public key so their signatures verify.

    Returns ``(destination_path, previous_key)``; the replaced key is tracked
    in git, so it is recoverable with ``git checkout``.

    Raises:
        ValueError: the source is not a usable Ed25519 public key.
    """
    key = _validated_key(source)
    destination = Path(peer_public_key_path(own_role, peer_role, _root(config_root)))
    existed = destination.exists()
    previous = destination.read_text(encoding="utf-8").strip() if existed else None
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(key + "\n", encoding="utf-8")
    return str(destination), previous


def _parse(argv):
    parser = argparse.ArgumentParser(
        description="Prepare this checkout for a live league match."
    )
    parser.add_argument("--public-url", help="our ngrok/Localtonet tunnel URL")
    parser.add_argument("--opponent-key", help="path to the opponent's .pub key")
    parser.add_argument("--role", default="police", choices=tuple(ENGINE_ROLE))
    parser.add_argument("--config-root", default=None)
    args = parser.parse_args(argv)
    if not (args.public_url or args.opponent_key):
        parser.error("nothing to do: pass --public-url and/or --opponent-key")
    return args


def main(argv=None):
    """Run whichever pre-game steps were asked for, then say what is left."""
    args = _parse(argv)
    if args.opponent_key:
        _validated_key(args.opponent_key)  # fail before mutating anything

    if args.public_url:
        was, now = set_public_url(args.public_url, args.role, args.config_root)
        print(f"[ok] advertising {args.role} at {now}\n     (was {was})")

    if args.opponent_key:
        where, previous = install_opponent_key(
            args.opponent_key, config_root=args.config_root
        )
        print(f"[ok] opponent key installed at {where}")
        print(f"     replaced {previous[:16] if previous else 'nothing'}...")

    print("\nThis checkout is ready for the parts above. Still MANUAL:")
    print("  * opponent_url in config/<role>/game.toml -> their tunnel URL")
    print("  * public_url   in config/<role>/game.toml -> your tunnel URL")
    print("  * start ngrok, then run scripts.run_remote_mcp_match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
