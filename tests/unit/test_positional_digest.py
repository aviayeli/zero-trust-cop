"""R1: the reveal digest is positional concatenation, per Rulebook 5.3.

    H = SHA256( State || Move || Intent || Nonce )

The previous form hashed sorted-key canonical JSON. Both self-verify, so our
own suite could never catch the mismatch -- both peers share one
implementation. Only an opposing team implementing 5.3 literally would have
found it, at which point every cross-team reveal fails.

verify() keeps a legacy fallback so artifacts sealed under the JSON form
still verify; commit() only ever emits the canonical positional form.
"""

import hashlib

import pytest

from mcp_server.crypto import canonical_json, commit, positional_payload, verify


def test_the_payload_is_literal_positional_concatenation():
    assert positional_payload("S0", "MOVE:N", "truth", "ab") == b"S0MOVE:Ntruthab"


def test_the_digest_is_sha256_of_that_exact_string():
    expected = hashlib.sha256(b"S0MOVE:Ntruthab").hexdigest()

    assert verify("S0", "MOVE:N", "truth", "ab", expected)


def test_commit_emits_the_positional_form(monkeypatch):
    monkeypatch.setattr("mcp_server.crypto.token_hex", lambda _: "cafe")

    digest, nonce = commit("S0", "MOVE:N", "truth")

    assert nonce == "cafe"
    assert digest == hashlib.sha256(b"S0MOVE:Ntruthcafe").hexdigest()


def test_a_genuine_reveal_round_trips():
    digest, nonce = commit("S1", "MOVE:W", "lie")

    assert verify("S1", "MOVE:W", "lie", nonce, digest)


@pytest.mark.parametrize("field, value", [
    ("state", "S9"), ("move", "MOVE:S"), ("intent", "lie"), ("nonce", "beef"),
])
def test_changing_any_bound_field_breaks_the_digest(field, value):
    fields = {"state": "S1", "move": "MOVE:W", "intent": "truth", "nonce": "ab"}
    digest = hashlib.sha256(
        positional_payload(**fields)
    ).hexdigest()
    fields[field] = value

    assert not verify(fields["state"], fields["move"], fields["intent"],
                      fields["nonce"], digest)


def test_a_legacy_json_sealed_digest_still_verifies():
    """Artifacts sealed before 5.3 alignment must not become unverifiable."""
    legacy = hashlib.sha256(canonical_json(
        {"state": "S1", "move": "MOVE:W", "intent": "truth", "nonce": "ab"}
    )).hexdigest()

    assert verify("S1", "MOVE:W", "truth", "ab", legacy)


def test_a_wrong_digest_fails_under_both_forms():
    assert not verify("S1", "MOVE:W", "truth", "ab", "00" * 32)
