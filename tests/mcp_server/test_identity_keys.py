"""Tests for per-peer Ed25519 key loading."""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key

from mcp_server.identity import (
    load_peer_public_key,
    load_signing_key,
    peer_public_key_path,
    signing_key_path,
)


def pem(private_key) -> bytes:
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def test_signing_key_paths_are_separated() -> None:
    police = signing_key_path("police")
    thief = signing_key_path("thief")
    assert police == "config/police/signing_key.pem"
    assert thief == "config/thief/signing_key.pem"
    assert police != thief


def test_signing_key_path_honours_explicit_config_root(tmp_path) -> None:
    assert signing_key_path("police", str(tmp_path)) == str(
        tmp_path / "police" / "signing_key.pem"
    )


def test_signing_key_path_honours_config_root_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ZTC_CONFIG_ROOT", str(tmp_path))
    assert signing_key_path("thief") == str(tmp_path / "thief" / "signing_key.pem")


def test_peer_public_key_paths_are_separated(tmp_path) -> None:
    police = peer_public_key_path("police", "thief", str(tmp_path))
    thief = peer_public_key_path("thief", "police", str(tmp_path))
    assert police == str(tmp_path / "police" / "peers" / "thief.pub")
    assert thief == str(tmp_path / "thief" / "peers" / "police.pub")
    assert police != thief


def test_load_signing_key_round_trip(tmp_path) -> None:
    key = Ed25519PrivateKey.generate()
    path = tmp_path / "police" / "signing_key.pem"
    path.parent.mkdir()
    path.write_bytes(pem(key))
    loaded = load_signing_key("police", str(tmp_path))
    signature = loaded.sign(b"message")
    key.public_key().verify(signature, b"message")


def test_load_peer_public_key_round_trip(tmp_path) -> None:
    key = Ed25519PrivateKey.generate()
    path = tmp_path / "police" / "peers" / "thief.pub"
    path.parent.mkdir(parents=True)
    path.write_text(key.public_key().public_bytes_raw().hex())
    loaded = load_peer_public_key("police", "thief", str(tmp_path))
    loaded.verify(key.sign(b"message"), b"message")


@pytest.mark.parametrize("loader, args", [
    (load_signing_key, ("police",)),
    (load_peer_public_key, ("police", "thief")),
])
def test_missing_key_files_raise(loader, args, tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        loader(*args, str(tmp_path))


def test_malformed_private_key_raises(tmp_path) -> None:
    path = tmp_path / "police" / "signing_key.pem"
    path.parent.mkdir()
    path.write_bytes(b"garbage")
    with pytest.raises(ValueError):
        load_signing_key("police", str(tmp_path))


@pytest.mark.parametrize("contents", ["not hexadecimal", "00" * 31])
def test_malformed_public_key_raises(contents, tmp_path) -> None:
    path = tmp_path / "police" / "peers" / "thief.pub"
    path.parent.mkdir(parents=True)
    path.write_text(contents)
    with pytest.raises(ValueError):
        load_peer_public_key("police", "thief", str(tmp_path))


def test_non_ed25519_private_key_raises(tmp_path) -> None:
    path = tmp_path / "police" / "signing_key.pem"
    path.parent.mkdir()
    path.write_bytes(pem(generate_private_key(public_exponent=65537, key_size=2048)))
    with pytest.raises(ValueError, match="Ed25519"):
        load_signing_key("police", str(tmp_path))


def test_unknown_role_is_rejected() -> None:
    with pytest.raises(ValueError):
        signing_key_path("referee")
