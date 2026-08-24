"""Validation for the league's ``reference-v3`` wire messages (SPEC §7.5).

Our own dialect (``submit_commitment`` / ``reveal_move`` / ``get_observation``
/ ``get_match_status``) and this one are BOTH served, so an opponent on either
surface can reach us. Compare tool lists before comparing anything inside
them: two peers can agree all fourteen terms, verify each other's signatures
and bring up both tunnels, and still exchange nothing because their surfaces
intersect only at ``negotiate``.

Everything here is pure validation -- no state is touched. That ordering is
the contract: a message is judged before it can change anything, so a refusal
never leaves a half-applied turn behind.

The refusal strings are the published fixture's own verdicts. They are
compared against ``tests/fixtures/interop/turn_message.json`` rather than
invented here, so our wording cannot drift away from the contract quietly.
"""

from __future__ import annotations

ACCEPT = "accept"
SENDERS = ("police", "thief")

TURN_REQUIRED = ("step", "sender", "hint", "smell_grid", "commit", "timestamp")
TURN_OPTIONAL = ("barrier_placed", "capture_claim", "claim_response", "win_claim")

# A step is a ROUND -- one action from each side -- not a half-turn. Stated as
# a constant because it is the desync no gate on either side would report.
STEP_SEMANTICS = (
    "step is a ROUND (one action from each side), not a half-turn: "
    "max_steps 35 means 35 moves EACH"
)


def _is_commit(value) -> bool:
    """64 lowercase hex characters. Compared as a STRING, so case matters."""
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _is_smell_grid(value) -> bool:
    """``{'r,c': intensity}``. A stringified intensity survives JSON and then
    poisons the physics check, so numbers are required here, not coerced."""
    if not isinstance(value, dict):
        return False
    for cell, intensity in value.items():
        if not isinstance(cell, str) or cell.count(",") != 1:
            return False
        if isinstance(intensity, bool) or not isinstance(intensity, (int, float)):
            return False
    return True


def _sender_ok(value) -> bool:
    return value in SENDERS


def _check(message, rules) -> str:
    """First failing rule's verdict, or ``accept``.

    A missing required key is REFUSED, never defaulted: a defaulted ``commit``
    is a move the sender never sealed. An UNKNOWN key is tolerated and ignored
    -- the extension seam. A receiver that refuses unknown keys cannot be
    extended without a flag day, so nothing here rejects on extra fields.
    """
    if not isinstance(message, dict):
        return "message: required object"
    for field, (ok, verdict) in rules.items():
        if field not in message or not ok(message[field]):
            return verdict
    return ACCEPT


def validate_turn_message(message) -> str:
    """One ``TurnMessage`` -- one message per half-turn."""
    return _check(message, {
        "step": (
            lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0,
            "step: required non-negative int",
        ),
        "sender": (_sender_ok, "sender: required 'police' | 'thief'"),
        # The hint may be EMPTY and may be a LIE (App. E permits deception in
        # the verbal channel). Absent is a different thing from empty.
        "hint": (lambda v: isinstance(v, str), "hint: required str"),
        "smell_grid": (
            _is_smell_grid, "smell_grid: required dict of 'r,c' -> number",
        ),
        "commit": (_is_commit, "commit: required 64-char lowercase hex"),
        # Decorative, load-bearing refusal: a peer sending an empty string here
        # is telling us its clock never ran.
        "timestamp": (
            lambda v: isinstance(v, str) and v.strip() != "",
            "timestamp: required non-empty str",
        ),
    })
