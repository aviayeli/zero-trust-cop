"""Session-lifecycle validation for ``reference-v3`` (SPEC §7.5).

Split from ``wire_v3`` by cadence: a TurnMessage crosses the wire once per
half-turn and lives there, while these three bracket the sub-game -- opening
it (``negotiate``), closing it (``submit_audit``) and reporting on it
(``receive_control``). The shared validation kernel stays in ``wire_v3``.

Every message on this wire arrives as ONE envelope argument. The kit's client
wraps its arguments under a single key, so a tool declaring flat parameters
fails Pydantic validation on the CALLER's side before our code is reached --
the arity is part of the contract, not an implementation detail.
"""

from __future__ import annotations

from mcp_server.wire_v3 import ACCEPT, _check, _sender_ok

AUDIT_REQUIRED = ("sender", "records", "result_claim")
CONTROL_REQUIRED = ("kind", "sender")
_AUDIT_RECORD_KEYS = ("payload", "nonce", "commit")

# `negotiate` carries the signed terms plus the pairing extras. The extras
# ride BESIDE `terms`, never inside it: the terms are a flat signed set, so an
# extra key there breaks the signature.
NEGOTIATE_REQUIRED = ("terms", "nonce", "signature")
NEGOTIATE_OPTIONAL = ("identity", "sub_game_number", "role")

def validate_audit_payload(payload) -> str:
    """One ``AuditPayload`` per sub-game: the sealed chain WITH nonces.

    ``result_claim`` is what this side believes the sub-game ended as. The
    opponent's audit settles it -- never the claim.
    """
    verdict = _check(payload, {
        "sender": (_sender_ok, "sender: required 'police' | 'thief'"),
        "records": (_records_ok, "records: required non-empty list"),
        "result_claim": (lambda v: isinstance(v, dict), "result_claim: required object"),
    })
    if verdict != ACCEPT:
        return verdict
    for record in payload["records"]:
        if not all(key in record for key in _AUDIT_RECORD_KEYS):
            return "records: each record needs payload, nonce, commit"
    return ACCEPT


def validate_negotiate(message) -> str:
    """The ``negotiate`` envelope: every argument under one key.

    The kit's client wraps all arguments in a single envelope rather than
    sending them flat, so a tool with flat parameters fails Pydantic
    validation on THEIR side before our code ever runs -- the arity is part
    of the wire contract, not an implementation detail.
    """
    return _check(message, {
        "terms": (lambda v: isinstance(v, dict) and bool(v),
                  "terms: required non-empty object"),
        "nonce": (lambda v: isinstance(v, str) and v != "",
                  "nonce: required non-empty str"),
        "signature": (lambda v: isinstance(v, str) and v != "",
                      "signature: required non-empty str"),
    })


def _records_ok(records) -> bool:
    return (
        isinstance(records, list)
        and bool(records)
        and all(isinstance(record, dict) for record in records)
    )


def validate_audit_payload(payload) -> str:
    """One ``AuditPayload`` per sub-game: the sealed chain WITH nonces.

    ``result_claim`` is what this side believes the sub-game ended as. The
    opponent's audit settles it -- never the claim.
    """
    verdict = _check(payload, {
        "sender": (_sender_ok, "sender: required 'police' | 'thief'"),
        "records": (_records_ok, "records: required non-empty list"),
        "result_claim": (lambda v: isinstance(v, dict), "result_claim: required object"),
    })
    if verdict != ACCEPT:
        return verdict
    for record in payload["records"]:
        if not all(key in record for key in _AUDIT_RECORD_KEYS):
            return "records: each record needs payload, nonce, commit"
    return ACCEPT


def validate_control_message(message) -> str:
    """A status channel touching no game state, never sealed and never scored."""
    return _check(message, {
        "kind": (lambda v: isinstance(v, str) and v != "", "kind: required non-empty str"),
        "sender": (_sender_ok, "sender: required 'police' | 'thief'"),
    })


def pairing_refusal(message: dict, our_role: str, our_uid: str | None) -> str | None:
    """Why this pairing must not start, or None.

    The handshake is the ONLY place a mispairing can be caught. Identical
    terms give identical ``game_uid``s, so two peers that both believe they
    are the thief agree on every signed byte and produce artifacts that join
    perfectly -- the contradiction surfaces only when a human reads the
    result.

    Both checks TOLERATE absence: the pairing fields are negotiate extras and
    declaring the uid is PROPOSED, not required. Only a declared
    CONTRADICTION is refused.
    """
    their_role = message.get("role")
    if their_role is not None and their_role == our_role:
        other = "thief" if our_role == "police" else "police"
        return (
            f"pairing: both peers declare role {our_role!r}. One must be "
            f"{our_role!r} and the other {other!r} -- check which endpoint "
            "you were given: our two peers listen on different ports."
        )

    declared = message.get("game_uid")
    if our_uid and declared and declared != our_uid:
        return (
            f"game_uid mismatch: ours {our_uid}, theirs {declared}. One side "
            "derived it from something other than the flat negotiated terms; "
            "a uid from the whole config is self-consistent across that "
            "peer's own artifacts and fails only the cross-team join."
        )
    return None
