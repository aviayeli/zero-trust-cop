"""Sender identity and terminal vocabulary across groups (PRD 21 Part 2).

Two validators used to reject a correct opponent outright: ``sender`` had to
be a role, and ``result_claim`` had to be an object. SMNGRP05 send the group
id and a bare string, and their argument for it is better than ours was --
their ``result_claim`` is compared downstream against the strings
"capture"/"survival"/"timeout", so a dict arriving there does not raise. It
compares unequal and SILENTLY MIS-SCORES the sub-game. A loud rejection is
recoverable; a silent mis-score is not.

ZeroOne0 separately call our "survival" an "escape". Both sides' claims agreed
on all six sub-games of a settled series while using different words for one
event seen from two seats.

=====================================================================
THE BOUNDARY -- the load-bearing property of this module.

Nothing here may ever touch bytes that are hashed. Commit preimages are built
by ``interop.canonical_str`` and ``crypto.reference_payload`` from the payload
AS RECEIVED. Normalising before hashing would change the digest and break
verification against every record already sealed: 406 of them across two
settled series, one of which is reported and published.

Vocabulary and whitespace live at the semantic layer, strictly above the hash.
=====================================================================
"""

from __future__ import annotations

# The seats within a live sub-game. Still meaningful -- a turn-level sender
# names a seat and is inside the hashed turn payload, which is why
# ``wire_v3``'s turn rule is deliberately NOT relaxed. Only the AUDIT-level
# sender is a filing identity, and a filing is made by a team.
ROLES = ("police", "thief")

# Our internal terminal vocabulary. ``technical_loss`` is here because the
# book makes it a real outcome (rule 19: a hash mismatch scores 0) -- refusing
# it would leave us unable to express a result we are required to be able to
# claim.
TERMINAL = ("capture", "survival", "timeout", "technical_loss")

# Other groups' words for the same events. Explicit and table-driven: an
# unknown word is REFUSED, never guessed. Guessing at an outcome is precisely
# how a sub-game gets mis-scored quietly, which is what this module exists to
# prevent.
ALIASES = {
    "escape": "survival",   # ZeroOne0: the same event named from the thief's seat
    "evade": "survival",
    "caught": "capture",
    "captured": "capture",
    "timed_out": "timeout",
    "time_out": "timeout",
    # OUR OWN engine's word. `match_state.terminal_reason` returns
    # 'max_moves_reached' where the wire says 'survival'. The reference-v3
    # loop translates before it claims, so this never reaches an audit today
    # -- but a path that forgot to translate should map, not be refused.
    "max_moves_reached": "survival",
}


def _word(value) -> str | None:
    """A comparable word, or None. Strips and lowercases for COMPARISON only;
    the stored value is never rewritten and never re-hashed."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower()
    return cleaned or None


def sender_ok(value) -> bool:
    """Whether ``sender`` identifies someone -- a role OR a group id.

    Neither spelling is privileged. A role names the seat; a group id names
    the filer, and the role alternates every sub-game, so a role does not
    identify who filed the audit.

    Relaxing WHICH string is accepted is not accepting a blank: empty,
    whitespace-only and non-strings stay refused. Silence was never
    acceptance and neither is a blank.
    """
    return _word(value) is not None


def outcome_of(claim) -> str | None:
    """The internal terminal word a claim means, or None if it means nothing.

    Accepts a bare string (SMNGRP05) or an object carrying ``outcome``
    (ours, alongside ``steps``). Returns None for anything unrecognised so
    the caller REFUSES rather than proceeding on a guess.
    """
    if isinstance(claim, dict):
        claim = claim.get("outcome")

    word = _word(claim)
    if word is None:
        return None
    word = ALIASES.get(word, word)
    return word if word in TERMINAL else None
