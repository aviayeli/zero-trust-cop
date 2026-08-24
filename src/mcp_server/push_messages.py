"""Validation for the push dialect's six inbound messages (PRD_09 FR1).

These shapes are ali-ahm1's, read from their live ``tools/list`` on
2026-08-24, not designed here. Two absences are deliberate and load-bearing,
and the tests pin them so nobody "fixes" them into requirements:

* ``receive_commit`` carries NO ``signature``. Our own dialect requires one,
  because a signature over ``{role, turn, h_commit}`` is what establishes WHO
  submitted a move. On this wire nothing does.
* ``receive_reveal`` carries NO ``nonce`` and NO ``state``. A reveal therefore
  cannot be checked against its commitment while the sub-game runs; nonces
  arrive in bulk at ``receive_final_audit``.

Both costs are recorded in PRD_09 and are why the dialect is opt-in.

Validation runs before any state change, an unknown key is tolerated (the
extension seam) and a missing required key is refused rather than defaulted.
"""

from __future__ import annotations

from mcp_server.wire_v3 import ACCEPT, _check, _is_commit, _sender_ok

# `step` is a PER-SENDER counter: each peer numbers its own chain and
# `max_steps: 35` means 35 moves EACH (agreed with ali-ahm1, 2026-08-24).
# Bounds are not enforced here -- the published contract only says
# non-negative, and refusing a legitimate step would stall a live game.
_STEP = (
    lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0,
    "step: required non-negative int",
)
_ROLE = (_sender_ok, "role: required 'police' | 'thief'")
_TEXT = "required non-empty str"

REVEAL_REQUIRED = ("role", "step", "move", "hint", "intent")


def _nonempty(field: str):
    return (lambda v: isinstance(v, str) and v != "", f"{field}: {_TEXT}")


def validate_commit(message) -> str:
    """``receive_commit(role, step, h_commit)`` -- no signature, by protocol."""
    return _check(message, {
        "role": _ROLE,
        "step": _STEP,
        "h_commit": (_is_commit, "h_commit: required 64-char lowercase hex"),
    })


def validate_reveal(message) -> str:
    """``receive_reveal(role, step, move, hint, intent)``.

    The hint may be EMPTY and may be a LIE -- App. E permits deception in the
    verbal channel -- but absent is a different thing from empty.
    """
    return _check(message, {
        "role": _ROLE,
        "step": _STEP,
        "move": _nonempty("move"),
        "hint": (lambda v: isinstance(v, str), "hint: required str"),
        "intent": _nonempty("intent"),
    })


def validate_ack(message) -> str:
    """``receive_ack(role, step)`` -- touches no engine state."""
    return _check(message, {"role": _ROLE, "step": _STEP})


def validate_capture_claim(message) -> str:
    """``receive_capture_claim(role, claimed)``.

    ``claimed`` is left loosely typed on purpose: their signature does not say
    whether it is a boolean or a coordinate, and refusing the wrong guess
    would stall the game over a field we do not adjudicate. Presence is
    required; shape is not.
    """
    return _check(message, {
        "role": _ROLE,
        "claimed": (lambda v: v is not None, "claimed: required"),
    })


def validate_step0(message) -> str:
    """``receive_step0(role, declaration, signature)``.

    The one message on this wire that DOES carry a signature -- over the
    declaration, once, rather than over each turn.
    """
    return _check(message, {
        "role": _ROLE,
        "declaration": (lambda v: isinstance(v, dict),
                        "declaration: required object"),
        "signature": _nonempty("signature"),
    })


def validate_final_audit(message) -> str:
    """``receive_final_audit(role, nonces)`` -- the whole sub-game's nonces.

    What the entries CARRY is still unknown (TODO 9.5): without the payload
    each ``h_commit`` sealed, the deferred audit cannot be recomputed at all.
    The list is checked for presence here; whether it is sufficient is decided
    at audit time, which reports ``unverifiable`` rather than guessing.
    """
    return _check(message, {
        "role": _ROLE,
        "nonces": (lambda v: isinstance(v, list) and bool(v),
                   "nonces: required non-empty list"),
    })
