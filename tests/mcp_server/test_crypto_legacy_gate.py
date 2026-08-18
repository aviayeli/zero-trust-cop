"""The superseded JSON payload form must be opt-in (audit T-1).

``verify`` accepted BOTH the Rulebook-5.3 positional concatenation and a
superseded sorted-key JSON encoding, unconditionally. Nothing has emitted the
JSON form since the 5.3 alignment, so on the live wire it was pure attack
surface: a peer could commit under an encoding this project no longer speaks
and still be honoured, and the two forms hash the same fields differently.

The fallback still has one legitimate reader — artifacts sealed before the
alignment must stay verifiable — so it is gated rather than deleted, and the
gate is keyword-only so no call site can enable it by accident.
"""

import hashlib

import pytest

from mcp_server.commitments import CommitmentBook
from mcp_server.crypto import canonical_json, commit, verify

STATE = "turn-0|(0, 0)|(3, 3)"
MOVE = "MOVE:N"
INTENT = "truth"
NONCE = "ab"


def _legacy_digest(state=STATE, move=MOVE, intent=INTENT, nonce=NONCE) -> str:
    """Seal a digest the way artifacts predating the 5.3 alignment were."""
    return hashlib.sha256(
        canonical_json(
            {"state": state, "move": move, "intent": intent, "nonce": nonce}
        )
    ).hexdigest()


def test_a_legacy_digest_is_refused_by_default():
    """The live wire speaks 5.3 only; anything else is not our protocol."""
    assert verify(STATE, MOVE, INTENT, NONCE, _legacy_digest()) is False


def test_a_legacy_digest_verifies_when_explicitly_allowed():
    """Pre-alignment evidence must not become unverifiable."""
    assert verify(
        STATE, MOVE, INTENT, NONCE, _legacy_digest(), allow_legacy=True
    ) is True


def test_the_positional_form_verifies_under_either_setting():
    h_commit, nonce = commit(STATE, MOVE, INTENT)

    assert verify(STATE, MOVE, INTENT, nonce, h_commit) is True
    assert verify(STATE, MOVE, INTENT, nonce, h_commit, allow_legacy=True) is True


def test_the_gate_cannot_be_passed_positionally():
    """Keyword-only, so a sixth argument can never silently re-open it."""
    with pytest.raises(TypeError):
        verify(STATE, MOVE, INTENT, NONCE, _legacy_digest(), True)


def test_a_wrong_digest_fails_even_with_the_gate_open():
    assert verify(STATE, MOVE, INTENT, NONCE, "00" * 32, allow_legacy=True) is False


def test_the_live_protocol_refuses_a_legacy_sealed_commitment():
    """The gate has to hold where it matters: the commit-reveal state machine."""
    book = CommitmentBook()
    thief_hash, _ = commit(STATE, "MOVE:S", INTENT)
    book.commit("police", 0, _legacy_digest())
    book.commit("thief", 0, thief_hash)

    outcome = book.reveal("police", 0, STATE, MOVE, INTENT, NONCE)

    assert outcome.status == "rejected"
    assert outcome.reason == "broken_commitment"
