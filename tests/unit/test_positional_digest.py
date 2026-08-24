"""Superseded commit encodings stay VERIFIABLE, and stay un-emitted.

Three forms have been the emitted one at different times:

1. the book ch.5 listing -- nonce sealed inside the canonical object;
2. Rulebook 5.3 positional concatenation, ``State || Move || Intent || Nonce``;
3. the league reference form, ``canonical({state,move,intent}) | nonce`` (now).

Each supersession leaves sealed artifacts behind, and evidence that stops
verifying is evidence destroyed -- so ``verify`` keeps 1 and 2 behind the
``allow_legacy`` gate. The gate is what stops them being a live-wire
liability: three encodings of the same fields, two the project no longer
speaks, all three accepted, is a peer's choice of which to commit under.

The emitted form itself is pinned in ``mcp_server/test_crypto_reference_form.py``
and against the shared league vectors in ``mcp_server/test_interop_vectors.py``.
"""

import hashlib

import pytest

from mcp_server.crypto import canonical_json, commit, positional_payload, verify

FIELDS = {"state": "S1", "move": "MOVE:W", "intent": "truth", "nonce": "ab"}


def _positional(**fields) -> str:
    return hashlib.sha256(positional_payload(**fields)).hexdigest()


def _nonce_sealed(**fields) -> str:
    return hashlib.sha256(canonical_json(fields)).hexdigest()


def test_the_positional_payload_is_literal_concatenation():
    assert positional_payload("S0", "MOVE:N", "truth", "ab") == b"S0MOVE:Ntruthab"


def test_concatenation_ran_adjacent_fields_together():
    """Why form 2 was superseded: no delimiters, so two distinct reveals share
    one preimage. Kept as a test because it is the reason, not a trivium."""
    assert positional_payload("ab", "c", "truth", "n") == \
        positional_payload("a", "bc", "truth", "n")


@pytest.mark.parametrize("seal", [_positional, _nonce_sealed],
                         ids=["positional-5.3", "ch5-nonce-sealed"])
def test_a_superseded_digest_is_refused_by_default(seal):
    """The live wire speaks the reference form only (audit T-1)."""
    assert verify(**FIELDS, h_commit=seal(**FIELDS)) is False


@pytest.mark.parametrize("seal", [_positional, _nonce_sealed],
                         ids=["positional-5.3", "ch5-nonce-sealed"])
def test_a_superseded_digest_verifies_behind_the_gate(seal):
    """Artifacts sealed under an earlier form must not become unverifiable."""
    assert verify(**FIELDS, h_commit=seal(**FIELDS), allow_legacy=True) is True


@pytest.mark.parametrize("seal", [_positional, _nonce_sealed],
                         ids=["positional-5.3", "ch5-nonce-sealed"])
@pytest.mark.parametrize("field, value", [
    ("state", "S9"), ("move", "MOVE:S"), ("intent", "lie"), ("nonce", "beef"),
])
def test_the_gate_still_binds_every_field(seal, field, value):
    """Opening the gate widens which ENCODINGS are accepted, never which
    values -- a legacy digest must not verify against a rewritten record."""
    tampered = {**FIELDS, field: value}

    assert verify(**tampered, h_commit=seal(**FIELDS), allow_legacy=True) is False


def test_a_wrong_digest_fails_under_every_form():
    assert verify(**FIELDS, h_commit="00" * 32, allow_legacy=True) is False


def test_the_emitted_form_needs_no_gate():
    h_commit, nonce = commit("S1", "MOVE:W", "truth")

    assert verify("S1", "MOVE:W", "truth", nonce, h_commit) is True
