"""Ed25519 signing and verification for authenticated peer submissions."""

import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from mcp_server.crypto import canonical_json

PEER_ROLES = ("police", "thief")


def _validate_role(role: str) -> None:
    if role not in PEER_ROLES:
        raise ValueError(f"Unknown peer role: {role}")


def _config_root(config_root: str | None) -> str:
    return config_root if config_root is not None else os.environ.get(
        "ZTC_CONFIG_ROOT", "config"
    )


def signing_key_path(role: str, config_root: str | None = None) -> str:
    """Return the private signing-key path for one peer workspace."""
    _validate_role(role)
    return os.path.join(_config_root(config_root), role, "signing_key.pem")


def peer_public_key_path(
    own_role: str, peer_role: str, config_root: str | None = None
) -> str:
    """Return the public-key path for a peer in an own-role workspace."""
    _validate_role(own_role)
    _validate_role(peer_role)
    return os.path.join(_config_root(config_root), own_role, "peers", f"{peer_role}.pub")


def load_signing_key(role: str, config_root: str | None = None) -> Ed25519PrivateKey:
    """Load this peer's Ed25519 private key, failing loudly on any problem."""
    with open(signing_key_path(role, config_root), "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(), password=None
        )
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("Private signing key must be an Ed25519 key")
    return private_key


def load_peer_public_key(
    own_role: str, peer_role: str, config_root: str | None = None
) -> Ed25519PublicKey:
    """Load a peer's raw-hex Ed25519 public key, failing loudly on invalid input."""
    with open(peer_public_key_path(own_role, peer_role, config_root)) as key_file:
        raw_hex = key_file.read().strip()
    try:
        public_bytes = bytes.fromhex(raw_hex)
    except ValueError as exc:
        raise ValueError("Peer public key must be valid hexadecimal") from exc
    if len(public_bytes) != 32:
        raise ValueError("Peer public key must contain exactly 32 bytes")
    return Ed25519PublicKey.from_public_bytes(public_bytes)


def sign(private_key, role: str, turn: int, h_commit: str) -> str:
    """Return a lowercase hexadecimal signature binding a submission to its turn."""
    message = canonical_json({"role": role, "turn": turn, "h_commit": h_commit})
    return private_key.sign(message).hex()


def verify_signature(
    public_key, role: str, turn: int, h_commit: str, signature: str
) -> bool:
    """Return whether signature authenticates the specified submission."""
    try:
        message = canonical_json({"role": role, "turn": turn, "h_commit": h_commit})
        public_key.verify(bytes.fromhex(signature), message)
    except (ValueError, InvalidSignature):
        return False
    return True
