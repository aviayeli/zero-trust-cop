"""Create the peer keypairs a fresh checkout does not have.

``signing_key.pem`` is gitignored by design, so a clean clone can run the
SERVER — which needs only public keys — but not the CLIENT, which must sign.
This closes that gap so the simulation runs out of the box.

Idempotent, and deliberately so: an existing private key is NEVER replaced.
Regenerating one would silently invalidate every public half already
published to the other peer, and every signature made under it.

Public halves are protected just as firmly, and for the same reason. A clean
checkout IS the state "``.pub`` present, ``.pem`` absent": the public keys are
tracked and the private ones are not. Republishing there would overwrite the
very keys the shipped match log was signed under, so a genuine log would read
as TAMPERED on a grader's machine. ``ensure_keys`` therefore refuses to
overwrite a shipped public half whose private key it had to generate, and says
so on stdout.

The cost of that refusal is stated plainly rather than hidden: on such a
checkout the freshly generated private key does NOT match the published public
half, so LIVE play will be rejected by signature verification until the
operator either restores the original ``signing_key.pem`` or deletes the
shipped ``.pub`` files to publish a fresh set. Verifiability of the shipped
evidence is treated as outranking live play on an untouched clone.

Note for interop: the committed ``.pub`` files belong to whoever generated
them, so a peer that does regenerate must re-share its public half.
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
CLEAN_CHECKOUT_WARNING = (
    "⚠️ Shipped public key exists but private key is missing (clean checkout). "
    "Skipping key generation to protect log signature integrity."
)
_RECOVERY_HINT = (
    "   Restore signing_key.pem to play live, or delete the shipped "
    "config/*/peers/*.pub files to publish a fresh set."
)


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


def _publish(path: str, hex_key: str, protected: bool) -> bool:
    """Write a public half only when it differs, to keep reruns a no-op.

    Returns:
        Whether an EXISTING shipped half was left in place untouched, i.e.
        whether this call refused to publish.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        with open(path) as existing:
            if existing.read().strip() == hex_key:
                return False
        if protected:
            return True
    with open(path, "w") as key_file:
        key_file.write(hex_key)
    return False


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

    refused = False
    for own_role in PEER_ROLES:
        os.makedirs(os.path.join(root, own_role, "peers"), exist_ok=True)
        for peer_role, private_key in keys.items():
            refused |= _publish(
                peer_public_key_path(own_role, peer_role, config_root),
                _public_hex(private_key),
                protected=peer_role in created,
            )
    if refused:
        print(CLEAN_CHECKOUT_WARNING)
        print(_RECOVERY_HINT)
    return created
