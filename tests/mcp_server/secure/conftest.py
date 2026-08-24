"""Fixtures for the authenticated tool-surface tests.

Tests generate their OWN Ed25519 keypairs and Q-tables into a tmp config root
rather than reading ``config/<role>/signing_key.pem`` (gitignored by design)
or ``data/`` (committed deliverables). A suite that depended on either would
pass here and fail in a clean checkout, or corrupt a shipped artifact.
"""

import re
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from engine.config import load_config
from mcp_server.crypto import commit
from mcp_server.identity import sign
from mcp_server.server import create_app
from strategy.qvalues import QValues
from strategy.settings import load_strategy_settings

PEER_ROLES = ("police", "thief")


def _public_hex(private_key):
    raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return raw.hex()


def _seed_table(root, role):
    """Write a small but genuinely non-empty table at the redirected path."""
    config = load_config(str(root / role / "game.json"))
    settings = load_strategy_settings(role, str(root))
    qvalues = QValues(config, settings)
    qvalues.q_table[((None, 0), "N")] = 1.0
    qvalues.q_table[((None, 0), "S")] = 2.0
    qvalues.save()


def _write_strategy(root, role):
    """Copy the peer's [strategy] block with qtable_path redirected to tmp."""
    source = Path(f"config/{role}/game.toml").read_text()
    table_path = root / role / "q_table.json"
    (root / role / "game.toml").write_text(
        re.sub(r'qtable_path = ".*"', f'qtable_path = "{table_path}"', source)
    )
    _seed_table(root, role)


@pytest.fixture
def peer_keys():
    """A fresh private key per peer, kept in memory for signing."""
    return {role: Ed25519PrivateKey.generate() for role in PEER_ROLES}


@pytest.fixture
def secure_config_root(tmp_path, peer_keys):
    """A config root where each peer holds both public keys and a table."""
    shared = Path("config/game.json").read_text()
    # `identity` rides in negotiate, so a peer needs its declaration — and
    # the root contract build_declaration reads the league block from.
    (tmp_path / "declaration.json").write_text(
        Path("config/declaration.json").read_text()
    )
    (tmp_path / "game.json").write_text(shared)
    for role in PEER_ROLES:
        peers_dir = tmp_path / role / "peers"
        peers_dir.mkdir(parents=True)
        (tmp_path / role / "game.json").write_text(shared)
        for peer, key in peer_keys.items():
            (peers_dir / f"{peer}.pub").write_text(_public_hex(key))
        _write_strategy(tmp_path, role)
    return str(tmp_path)


@pytest.fixture
def app(secure_config_root):
    """A police peer wired against the generated keys and table."""
    return create_app("police", config_root=secure_config_root)


@pytest.fixture
def make_commitment():
    """Build a signed commitment plus everything needed to reveal it."""

    def build(key, role, turn, move="N", intent="truth", state="s0"):
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


class HandCrankedClock:
    """A monotonic clock the test advances explicitly; nothing ever sleeps."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def forfeit_clock():
    return HandCrankedClock()


@pytest.fixture
def forfeit_app(secure_config_root, forfeit_clock):
    """A police peer whose commitment book runs on the injected clock."""
    return create_app("police", config_root=secure_config_root, clock=forfeit_clock)


@pytest.fixture
def commitment_pair(make_commitment, peer_keys):
    """Both peers' signed commitments for turn 0."""
    return (
        make_commitment(peer_keys["police"], "police", 0),
        make_commitment(peer_keys["thief"], "thief", 0),
    )
