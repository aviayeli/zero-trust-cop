"""The emitted commit is the league's reference form, not the ch.5 listing.

    h_commit = SHA256( canonical_json({state, move, intent}) | nonce )

The book publishes three inconsistent constructions. We previously emitted the
positional one, ``SHA256(State || Move || Intent || Nonce)`` -- undelimited, so
field boundaries were positional only (PLAN.md §10.2). The community interop
kit pins the lecturer's reference form, which is what the opponent's audit
re-hashes our revealed records under.

Both forms self-verify, so our own suite could never catch the divergence: one
implementation sits on both sides of every local test. Only the opponent's
audit finds it, and by then a clean match is scored as tampering for BOTH
sides. Hence the fixture-bound tests in ``test_interop_vectors.py`` -- these
here only pin OUR call sites onto that construction.
"""

import hashlib
import json

import pytest

from mcp_server import interop
from mcp_server.crypto import commit, positional_payload, verify

STATE = "turn-0|(0, 0)|(3, 3)"
MOVE = "MOVE:N"
INTENT = "truth"


def _reference(state, move, intent, nonce) -> str:
    """Recomputed from a literal f-string, independently of the module, so the
    test cannot drift along with the code it pins."""
    canonical = json.dumps(
        {"intent": intent, "move": move, "state": state},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(f"{canonical}|{nonce}".encode()).hexdigest()


def test_commit_emits_the_reference_form(monkeypatch):
    monkeypatch.setattr("mcp_server.crypto.token_hex", lambda _: "cafe")

    digest, nonce = commit(STATE, MOVE, INTENT)

    assert nonce == "cafe"
    assert digest == _reference(STATE, MOVE, INTENT, "cafe")


def test_the_emitted_form_agrees_with_the_shared_interop_construction():
    """Our per-turn seal and the cross-team primitive must not drift apart."""
    digest, nonce = commit(STATE, MOVE, INTENT)

    assert digest == interop.commit(
        {"state": STATE, "move": MOVE, "intent": INTENT}, nonce
    )


def test_a_genuine_reveal_round_trips():
    digest, nonce = commit(STATE, MOVE, INTENT)

    assert verify(STATE, MOVE, INTENT, nonce, digest) is True


def test_a_non_ascii_intent_is_sealed_as_native_utf8():
    """ensure_ascii=False, the kit's single most important detail: an escaped
    \\uXXXX payload hashes differently, so the opponent's audit re-hash misses
    and reads a clean record as tampering."""
    hebrew = "אני ליד הכיכר 🙂"
    digest, nonce = commit(STATE, MOVE, hebrew)

    assert digest == _reference(STATE, MOVE, hebrew, nonce)
    assert verify(STATE, MOVE, hebrew, nonce, digest) is True


@pytest.mark.parametrize("field, value", [
    ("state", "S9"), ("move", "MOVE:S"), ("intent", "lie"), ("nonce", "beef"),
])
def test_changing_any_bound_field_breaks_the_digest(field, value):
    fields = {"state": "S1", "move": "MOVE:W", "intent": "truth", "nonce": "ab"}
    digest = _reference(**fields)
    fields[field] = value

    assert verify(fields["state"], fields["move"], fields["intent"],
                  fields["nonce"], digest) is False


def test_the_canonical_form_delimits_fields_that_concatenation_ran_together():
    """The old positional form's documented weakness (PLAN.md §10.2): with no
    delimiters, ("ab","c") and ("a","bc") produce ONE preimage. The canonical
    form separates them, so this is now a real fix, not a caveat."""
    assert positional_payload("ab", "c", INTENT, "n") == \
        positional_payload("a", "bc", INTENT, "n")

    left, nonce = commit("ab", "c", INTENT)

    assert verify("a", "bc", INTENT, nonce, left) is False


# --- the superseded forms, gated ------------------------------------------


def _positional_digest(nonce) -> str:
    return hashlib.sha256(f"{STATE}{MOVE}{INTENT}{nonce}".encode()).hexdigest()


def test_the_positional_form_is_refused_by_default():
    """It is now legacy: the live wire speaks the reference form only."""
    assert verify(STATE, MOVE, INTENT, "ab", _positional_digest("ab")) is False


def test_the_positional_form_verifies_behind_the_gate():
    """Artifacts sealed under 5.3 must not become unverifiable."""
    assert verify(STATE, MOVE, INTENT, "ab", _positional_digest("ab"),
                  allow_legacy=True) is True


def test_the_gate_cannot_be_passed_positionally():
    with pytest.raises(TypeError):
        verify(STATE, MOVE, INTENT, "ab", _positional_digest("ab"), True)
