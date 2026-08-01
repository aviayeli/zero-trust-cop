"""Fixtures for the authenticated tool-surface tests.

Tests generate their OWN Ed25519 keypairs into a tmp config root rather than
reading ``config/<role>/signing_key.pem``, which is gitignored by design. A
suite that depended on operator-local secrets would pass here and fail in any
clean checkout.
"""

from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mcp_server.crypto import commit
from mcp_server.identity import sign
from mcp_server.server import create_app

PEER_ROLES = ("police", "thief")


def _public_hex(private_key):
    raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return raw.hex()


@pytest.fixture
def peer_keys():
    """A fresh private key per peer, kept in memory for signing."""
    return {role: Ed25519PrivateKey.generate() for role in PEER_ROLES}


@pytest.fixture
def secure_config_root(tmp_path, peer_keys):
    """A config root where each peer workspace holds BOTH public keys."""
    shared = Path("config/game.json").read_text()
    for role in PEER_ROLES:
        peers_dir = tmp_path / role / "peers"
        peers_dir.mkdir(parents=True)
        (tmp_path / role / "game.json").write_text(shared)
        for peer, key in peer_keys.items():
            (peers_dir / f"{peer}.pub").write_text(_public_hex(key))
    return str(tmp_path)


@pytest.fixture
def app(secure_config_root):
    """A police peer wired against the generated keys."""
    return create_app("police", config_root=secure_config_root)


@pytest.fixture
def make_commitment():
    """Build a signed commitment plus everything needed to reveal it."""

    def build(key, role, turn, move="N", intent="north", state="s0"):
        digest, nonce = commit(state, move, intent)
        return {
            "role": role,
            "turn": turn,
            "h_commit": digest,
            "nonce": nonce,
            "signature": sign(key, role, turn, digest),
            "state": state,
            "move": move,
            "intent": intent,
        }

    return build
