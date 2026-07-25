"""Ed25519 signing and verification for authenticated peer submissions."""

from cryptography.exceptions import InvalidSignature

from mcp_server.crypto import canonical_json


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
