"""Create the peer keypairs a fresh checkout does not have.

``signing_key.pem`` is gitignored by design, so a clean clone can run the
SERVER — which needs only public keys — but not the CLIENT, which must sign.
This closes that gap so the simulation runs out of the box.

Idempotent, and deliberately so: an existing private key is NEVER replaced.
Regenerating one would silently invalidate every public half already
published to the other peer, and every signature made under it.

Note for interop: the committed ``.pub`` files belong to whoever generated
them. A checkout without the matching private keys necessarily produces new
ones, so the published public halves change and must be re-shared with any
external peer.
"""

import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mcp_server.identity import (
    PEER_ROLES,
    _config_root,
    load_signing_key,
    peer_public_key_path,
    signing_key_path,
)

_KEY_MODE = 0o600


def _write_private_key(path: str, private_key) -> None:
    """Write a PKCS8 PEM readable only by its owner."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    with open(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, _KEY_MODE), "wb") as key_file:
        key_file.write(pem)
    os.chmod(path, _KEY_MODE)


def _public_hex(private_key) -> str:
    raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return raw.hex()


def _publish(path: str, hex_key: str) -> None:
    """Write a public half only when it differs, to keep reruns a no-op."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        with open(path) as existing:
            if existing.read().strip() == hex_key:
                return
    with open(path, "w") as key_file:
        key_file.write(hex_key)


def ensure_keys(config_root: str | None = None) -> list:
    """Create any missing signing key, then republish every public half.

    Returns:
        The roles whose PRIVATE key was newly generated, in role order.
        Empty when every key was already present.
    """
    root = _config_root(config_root)
    created = []
    keys = {}

    for role in PEER_ROLES:
        path = signing_key_path(role, config_root)
        if os.path.exists(path):
            keys[role] = load_signing_key(role, config_root)
            continue
        private_key = Ed25519PrivateKey.generate()
        _write_private_key(path, private_key)
        keys[role] = private_key
        created.append(role)

    for own_role in PEER_ROLES:
        os.makedirs(os.path.join(root, own_role, "peers"), exist_ok=True)
        for peer_role, private_key in keys.items():
            _publish(
                peer_public_key_path(own_role, peer_role, config_root),
                _public_hex(private_key),
            )
    return created
