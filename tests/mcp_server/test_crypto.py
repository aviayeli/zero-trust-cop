"""Strict-TDD tests for mcp_server.crypto — the commit-reveal primitive.

Commit-reveal gives simultaneous-move integrity between two peers with no
trusted arbiter: each peer publishes h_commit first and reveals (move, intent,
nonce) only after both commitments are exchanged, so neither can adapt its move
to what it learned from the other.
"""

import hashlib
import json

import mcp_server.crypto as crypto
from mcp_server.crypto import commit, verify


STATE = "turn-7:cop=(0,0):thief=(3,3)"
MOVE = "N"
INTENT = "cut off the northern exit"


def _canonical(state, move, intent, nonce):
    """The exact wire serialization both peers must agree on, recomputed here
    independently of the implementation."""
    return json.dumps(
        {"state": state, "move": move, "intent": intent, "nonce": nonce},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


# --- commit ----------------------------------------------------------------


def test_commit_returns_digest_and_nonce():
    h_commit, nonce = commit(STATE, MOVE, INTENT)
    assert len(nonce) == 32          # 16 bytes rendered as hex
    assert len(h_commit) == 64       # sha-256 rendered as hex
    int(nonce, 16)                   # both must be valid hex
    int(h_commit, 16)


def test_commit_nonce_is_fresh_on_every_call():
    _, first = commit(STATE, MOVE, INTENT)
    _, second = commit(STATE, MOVE, INTENT)
    assert first != second


def test_commit_hides_the_move_across_calls():
    """Identical inputs must not yield identical commitments, or an opponent
    could recognise a repeated move from the published digest alone."""
    first, _ = commit(STATE, MOVE, INTENT)
    second, _ = commit(STATE, MOVE, INTENT)
    assert first != second


def test_digest_matches_independently_computed_positional_concatenation():
    """Pins the wire format (Rulebook 5.3): the other group must agree byte
    for byte. Computed here from a literal f-string rather than by calling the
    module's own helper, so the test cannot drift along with the code."""
    h_commit, nonce = commit(STATE, MOVE, INTENT)
    expected = hashlib.sha256(
        f"{STATE}{MOVE}{INTENT}{nonce}".encode()
    ).hexdigest()
    assert h_commit == expected


def test_a_legacy_json_sealed_digest_is_still_accepted():
    """Backwards compatibility: artifacts sealed before 5.3 must still verify."""
    nonce = "abc123"
    legacy = hashlib.sha256(_canonical(STATE, MOVE, INTENT, nonce)).hexdigest()
    assert verify(STATE, MOVE, INTENT, nonce, legacy) is True


# --- verify: honest reveal --------------------------------------------------


def test_verify_accepts_an_honest_reveal():
    h_commit, nonce = commit(STATE, MOVE, INTENT)
    assert verify(STATE, MOVE, INTENT, nonce, h_commit) is True


def test_verify_is_repeatable():
    h_commit, nonce = commit(STATE, MOVE, INTENT)
    assert verify(STATE, MOVE, INTENT, nonce, h_commit) is True
    assert verify(STATE, MOVE, INTENT, nonce, h_commit) is True


# --- verify: tampering ------------------------------------------------------


def test_verify_rejects_a_tampered_move():
    h_commit, nonce = commit(STATE, MOVE, INTENT)
    assert verify(STATE, "S", INTENT, nonce, h_commit) is False


def test_verify_rejects_a_tampered_nonce():
    h_commit, nonce = commit(STATE, MOVE, INTENT)
    forged = "1" * 32 if nonce != "1" * 32 else "2" * 32
    assert verify(STATE, MOVE, INTENT, forged, h_commit) is False


def test_verify_rejects_a_tampered_state():
    """Binding to state stops a commitment being replayed on a later turn."""
    h_commit, nonce = commit(STATE, MOVE, INTENT)
    assert verify("turn-8:cop=(1,0)", MOVE, INTENT, nonce, h_commit) is False


def test_verify_rejects_a_tampered_intent():
    h_commit, nonce = commit(STATE, MOVE, INTENT)
    assert verify(STATE, MOVE, "feint south instead", nonce, h_commit) is False


def test_verify_rejects_a_tampered_commitment():
    h_commit, nonce = commit(STATE, MOVE, INTENT)
    flipped = ("0" if h_commit[0] != "0" else "1") + h_commit[1:]
    assert verify(STATE, MOVE, INTENT, nonce, flipped) is False


def test_verify_rejects_garbage_commitment_without_raising():
    _, nonce = commit(STATE, MOVE, INTENT)
    assert verify(STATE, MOVE, INTENT, nonce, "not-a-digest") is False


def test_field_values_are_not_interchangeable():
    """Guards against an ambiguous encoding in which swapping two field values
    produces the same digest (the classic concatenation flaw)."""
    h_commit, nonce = commit("A", "B", INTENT)
    assert verify("B", "A", INTENT, nonce, h_commit) is False


# --- timing-attack guard ----------------------------------------------------


def test_verify_compares_in_constant_time(monkeypatch):
    """The comparison must go through secrets.compare_digest; a plain ==
    leaks via timing how many leading characters matched."""
    calls = []
    real = crypto.compare_digest

    def spy(left, right):
        calls.append((left, right))
        return real(left, right)

    monkeypatch.setattr(crypto, "compare_digest", spy)
    h_commit, nonce = commit(STATE, MOVE, INTENT)
    assert verify(STATE, MOVE, INTENT, nonce, h_commit) is True
    assert calls, "verify must compare via secrets.compare_digest"
