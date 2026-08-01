"""The exception wrappers must fail CLOSED.

Tested directly rather than through verify_log, because integration cannot
isolate them: a hostile h_commit also invalidates the signature, so the
commitment check failing open is masked by the signature check still firing.
Mutation testing found exactly that gap — `_safe_verify` returning True on
error survived the whole suite.

A security wrapper that fails OPEN turns a crash into a silent pass, which is
strictly worse than the crash it replaced.
"""

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.log_checks import _safe_signature, _safe_verify

_HOSTILE = [
    pytest.param({"state": "s", "move": "N", "intent": "i", "nonce": "n",
                  "h_commit": "ü" * 64}, id="non-ascii digest"),
    pytest.param({"state": "s", "move": "N", "intent": "i", "nonce": "n",
                  "h_commit": None}, id="null digest"),
    pytest.param({"state": "s", "move": "N", "intent": "i"}, id="fields missing"),
    pytest.param({}, id="empty entry"),
]


@pytest.mark.parametrize("entry", _HOSTILE)
def test_safe_verify_returns_false_rather_than_raising(entry):
    assert _safe_verify(entry) is False


@pytest.mark.parametrize("entry", _HOSTILE)
def test_safe_signature_returns_false_rather_than_raising(entry):
    public_key = Ed25519PrivateKey.generate().public_key()

    assert _safe_signature(public_key, "police", 0, entry) is False


def test_safe_verify_still_accepts_a_genuine_reveal():
    """Failing closed must not mean failing always."""
    from mcp_server.crypto import commit

    digest, nonce = commit("s0", "N", "north")

    assert _safe_verify({"state": "s0", "move": "N", "intent": "north",
                         "nonce": nonce, "h_commit": digest}) is True


def test_safe_signature_still_accepts_a_genuine_signature():
    from mcp_server.identity import sign

    key = Ed25519PrivateKey.generate()
    entry = {"h_commit": "abc", "signature": sign(key, "police", 3, "abc")}

    assert _safe_signature(key.public_key(), "police", 3, entry) is True
