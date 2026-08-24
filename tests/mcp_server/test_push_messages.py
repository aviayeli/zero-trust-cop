"""Validation for the push dialect's six inbound messages (PRD_09 FR1).

Same discipline as the reference-v3 surface, for the same reason: validation
runs BEFORE any state change, an unknown key is TOLERATED (the extension seam)
and a missing required key is REFUSED rather than defaulted. A defaulted
`h_commit` is a move the sender never sealed.

The shapes are ali-ahm1's, read from their live `tools/list` on 2026-08-24 --
not invented here. Their `receive_commit` carries no signature and their
`receive_reveal` no nonce, which is exactly what PRD_09 records as this
dialect's cost.
"""

import pytest

from mcp_server import push_messages as pm

COMMIT = "a" * 64


@pytest.mark.parametrize("role", ["police", "thief"])
def test_both_contract_roles_are_accepted(role):
    assert pm.validate_commit({"role": role, "step": 1, "h_commit": COMMIT}) == "accept"


@pytest.mark.parametrize("role", ["cop", "POLICE", "", None, 7])
def test_an_unknown_role_is_refused(role):
    """They say `police` / `thief` on the wire, as the book's contract does."""
    verdict = pm.validate_commit({"role": role, "step": 1, "h_commit": COMMIT})

    assert verdict == "role: required 'police' | 'thief'"


# --- receive_commit --------------------------------------------------------


@pytest.mark.parametrize("h_commit, why", [
    ("A" * 64, "uppercase hex: the commit is compared as a string"),
    ("a" * 63, "too short"),
    ("g" * 64, "not hex"),
    (None, "missing"),
    (12345, "not a string"),
])
def test_a_malformed_commit_is_refused(h_commit, why):
    verdict = pm.validate_commit({"role": "thief", "step": 1, "h_commit": h_commit})

    assert verdict == "h_commit: required 64-char lowercase hex", why


def test_a_missing_commit_key_is_refused_not_defaulted():
    assert pm.validate_commit({"role": "thief", "step": 1}) == \
        "h_commit: required 64-char lowercase hex"


def test_a_negative_step_is_not_a_step():
    assert pm.validate_commit({"role": "thief", "step": -1, "h_commit": COMMIT}) == \
        "step: required non-negative int"


def test_an_unknown_key_is_tolerated():
    assert pm.validate_commit(
        {"role": "thief", "step": 1, "h_commit": COMMIT, "future": {"x": 1}}
    ) == "accept"


# --- receive_reveal --------------------------------------------------------


def _reveal(**over):
    base = {"role": "thief", "step": 1, "move": "MOVE:N",
            "hint": "north of the park", "intent": "truth"}
    base.update(over)
    return base


def test_a_well_formed_reveal_is_accepted():
    assert pm.validate_reveal(_reveal()) == "accept"


def test_an_empty_hint_is_accepted_but_a_missing_one_is_not():
    """The hint may be empty and may be a lie; absent is a different thing."""
    assert pm.validate_reveal(_reveal(hint="")) == "accept"
    without = {k: v for k, v in _reveal().items() if k != "hint"}
    assert pm.validate_reveal(without) == "hint: required str"


@pytest.mark.parametrize("field", ["move", "intent"])
def test_a_reveal_missing_a_bound_field_is_refused(field):
    without = {k: v for k, v in _reveal().items() if k != field}

    assert pm.validate_reveal(without) == f"{field}: required non-empty str"


def test_a_reveal_carries_no_nonce_and_that_is_expected(_=None):
    """PRD_09: the nonce is absent by protocol, collected at final audit.
    Pinned so nobody 'fixes' the validator by demanding one."""
    assert "nonce" not in pm.REVEAL_REQUIRED
    assert "state" not in pm.REVEAL_REQUIRED
    assert pm.validate_reveal(_reveal()) == "accept"


# --- ack / capture claim / step0 / final audit -----------------------------


def test_an_ack_needs_only_role_and_step():
    assert pm.validate_ack({"role": "police", "step": 3}) == "accept"
    assert pm.validate_ack({"role": "police"}) == "step: required non-negative int"


def test_a_capture_claim_must_state_something():
    assert pm.validate_capture_claim({"role": "police", "claimed": True}) == "accept"
    assert pm.validate_capture_claim({"role": "police", "claimed": [3, 3]}) == "accept"
    assert pm.validate_capture_claim({"role": "police"}) == "claimed: required"


def test_step0_carries_a_declaration_and_a_signature():
    assert pm.validate_step0({"role": "thief", "declaration": {"group": "x"},
                              "signature": "ab"}) == "accept"
    assert pm.validate_step0({"role": "thief", "signature": "ab"}) == \
        "declaration: required object"


def test_a_final_audit_carries_a_non_empty_nonce_list():
    assert pm.validate_final_audit({"role": "thief", "nonces": ["ab"]}) == "accept"
    assert pm.validate_final_audit({"role": "thief", "nonces": []}) == \
        "nonces: required non-empty list"


def test_no_validator_raises_on_junk():
    for junk in ([], "x", None, 3):
        for check in (pm.validate_commit, pm.validate_reveal, pm.validate_ack,
                      pm.validate_capture_claim, pm.validate_step0,
                      pm.validate_final_audit):
            assert check(junk) == "message: required object"
