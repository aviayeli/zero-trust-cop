"""Tests for Ed25519 authentication of peer submissions."""

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mcp_server.crypto import canonical_json
from mcp_server.identity import sign, verify_signature

KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
OTHER_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
ROLE = "police"
TURN = 7
H_COMMIT = "9d991c9040ff8dc5a6616d6fb1c4a6e73e933c3eb0853dbd37c025a6991b345e"
SIGNATURE = (
    "07d8ccf196ffe6d4605922f9ae2cbfc68849c2c7be42c17355e1f2868715ad99"
    "534d86b2a7b8a466ed868bcef478b7c7843d06d6574bbf59d6d4c158b0fd9803"
)


def test_sign_matches_known_answer() -> None:
    assert sign(KEY, ROLE, TURN, H_COMMIT) == SIGNATURE


def test_verify_signature_round_trip() -> None:
    assert verify_signature(KEY.public_key(), ROLE, TURN, H_COMMIT, SIGNATURE)


def test_verify_signature_rejects_tampered_role() -> None:
    assert not verify_signature(KEY.public_key(), "criminal", TURN, H_COMMIT, SIGNATURE)


def test_verify_signature_rejects_replay_on_later_turn() -> None:
    """A signature made for turn 7 cannot be replayed as a turn-8 submission."""
    assert not verify_signature(KEY.public_key(), ROLE, TURN + 1, H_COMMIT, SIGNATURE)


def test_verify_signature_rejects_tampered_commitment() -> None:
    assert not verify_signature(KEY.public_key(), ROLE, TURN, "0" * 64, SIGNATURE)


def test_verify_signature_rejects_other_key() -> None:
    other_signature = sign(OTHER_KEY, ROLE, TURN, H_COMMIT)
    assert not verify_signature(KEY.public_key(), ROLE, TURN, H_COMMIT, other_signature)


@pytest.mark.parametrize("signature", ["not-a-signature", "00" * 63, ""])
def test_verify_signature_rejects_malformed_signatures(signature: str) -> None:
    assert not verify_signature(KEY.public_key(), ROLE, TURN, H_COMMIT, signature)


def test_verify_signature_rejects_invalid_public_key_loudly() -> None:
    """A misconfigured key must fail loudly per PRD_03 FR1."""
    with pytest.raises(AttributeError):
        verify_signature(None, ROLE, TURN, H_COMMIT, SIGNATURE)


def test_signature_uses_crypto_canonical_wire_format() -> None:
    signature = sign(KEY, ROLE, TURN, H_COMMIT)
    expected_bytes = canonical_json(
        {"role": ROLE, "turn": TURN, "h_commit": H_COMMIT}
    )
    KEY.public_key().verify(bytes.fromhex(signature), expected_bytes)
