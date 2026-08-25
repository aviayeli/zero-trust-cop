"""A clean checkout must be able to run the simulation unattended.

``signing_key.pem`` is gitignored by design, so a fresh clone can run the
SERVER — which needs only public keys — but not the CLIENT, which must sign.
``ensure_keys`` closes that gap without manual openssl steps.
"""

import os

from mcp_server.identity import (
    load_peer_public_key,
    load_signing_key,
    sign,
    verify_signature,
)
from mcp_server.keygen import ensure_keys

PEER_ROLES = ("police", "thief")


def test_a_bare_directory_gains_both_private_keys(tmp_path):
    created = ensure_keys(str(tmp_path))

    assert sorted(created) == ["police", "thief"]
    for role in PEER_ROLES:
        assert (tmp_path / role / "signing_key.pem").exists()


def test_every_workspace_receives_every_public_half(tmp_path):
    """A peer authenticates both sides of a turn, so it needs both keys."""
    ensure_keys(str(tmp_path))

    for own in PEER_ROLES:
        for peer in PEER_ROLES:
            assert (tmp_path / own / "peers" / f"{peer}.pub").exists()


def test_published_public_halves_match_their_private_keys(tmp_path):
    ensure_keys(str(tmp_path))

    for role in PEER_ROLES:
        private = load_signing_key(role, str(tmp_path))
        published = load_peer_public_key("police", role, str(tmp_path))
        signature = sign(private, role, 3, "digest")
        assert verify_signature(published, role, 3, "digest", signature)


def test_the_two_peers_get_different_keys(tmp_path):
    ensure_keys(str(tmp_path))

    police = (tmp_path / "police" / "peers" / "police.pub").read_text()
    thief = (tmp_path / "police" / "peers" / "thief.pub").read_text()

    assert police != thief


def test_rerunning_never_replaces_an_existing_private_key(tmp_path):
    """Regeneration would silently invalidate every published public half."""
    ensure_keys(str(tmp_path))
    before = {
        role: (tmp_path / role / "signing_key.pem").read_bytes()
        for role in PEER_ROLES
    }

    created = ensure_keys(str(tmp_path))

    assert created == []
    for role in PEER_ROLES:
        assert (tmp_path / role / "signing_key.pem").read_bytes() == before[role]


def test_a_missing_key_is_generated_without_disturbing_the_other(tmp_path):
    ensure_keys(str(tmp_path))
    thief_before = (tmp_path / "thief" / "signing_key.pem").read_bytes()
    (tmp_path / "police" / "signing_key.pem").unlink()

    created = ensure_keys(str(tmp_path))

    assert created == ["police"]
    assert (tmp_path / "thief" / "signing_key.pem").read_bytes() == thief_before


def test_a_regenerated_key_republishes_where_nothing_was_shipped(tmp_path):
    """With no shipped public half to protect, a new key must publish itself.

    The opposite case — a shipped ``.pub`` with no private key, i.e. a clean
    checkout — is deliberately NOT republished; see ``test_keygen_protection``.
    """
    ensure_keys(str(tmp_path))
    stale = (tmp_path / "police" / "peers" / "police.pub").read_text()
    (tmp_path / "police" / "signing_key.pem").unlink()
    for own in PEER_ROLES:
        (tmp_path / own / "peers" / "police.pub").unlink()

    ensure_keys(str(tmp_path))

    assert (tmp_path / "police" / "peers" / "police.pub").read_text() != stale


def test_the_private_key_is_not_world_readable(tmp_path):
    ensure_keys(str(tmp_path))

    mode = os.stat(tmp_path / "police" / "signing_key.pem").st_mode

    assert mode & 0o077 == 0, "private key must not be group- or world-readable"


def test_generated_keys_drive_a_real_peer(tmp_path):
    """The whole point: a bare directory becomes a usable peer workspace."""
    ensure_keys(str(tmp_path))

    private = load_signing_key("thief", str(tmp_path))
    public = load_peer_public_key("police", "thief", str(tmp_path))
    signature = sign(private, "thief", 0, "abc")

    assert verify_signature(public, "thief", 0, "abc", signature)
    assert not verify_signature(public, "thief", 1, "abc", signature)
