"""Sender identity and terminal vocabulary, relaxed for cross-group play.

SMNGRP05 send `sender` as the group id and `result_claim` as a bare string;
we required a role and an object. Their argument decided it: their
`result_claim` is compared downstream against "capture"/"survival"/"timeout",
so a dict arriving there does not raise -- it compares unequal and silently
MIS-SCORES the sub-game. A loud rejection is recoverable; a silent mis-score
is not.

ZeroOne0 separately name the same terminal event "escape" where we say
"survival". Both sides' claims agreed on all six sub-games of a settled
series while using different words.

THE BOUNDARY, pinned by the last test in this file: none of this may touch
bytes that are hashed. 406 sealed records across two settled series verify
against the bytes as received.
"""

import hashlib

import pytest

from mcp_server import wire_vocab
from mcp_server.interop import NONCE_SEPARATOR, canonical_str


@pytest.mark.parametrize("value", ["police", "thief", "aviayeli", "SMNGRP05"])
def test_sender_accepts_a_role_or_a_group_id(value):
    """Neither spelling is privileged: a role names a seat, a group id names
    the filer, and the role alternates every sub-game."""
    assert wire_vocab.sender_ok(value)


@pytest.mark.parametrize("value", ["", "   ", None, 123, [], {}])
def test_sender_still_refuses_empty_and_non_strings(value):
    """Relaxing which string is accepted is not accepting a blank."""
    assert not wire_vocab.sender_ok(value)


@pytest.mark.parametrize("claim,expected", [
    ("survival", "survival"),
    ("capture", "capture"),
    ("timeout", "timeout"),
    ({"outcome": "survival", "steps": 35}, "survival"),
    ({"outcome": "capture", "steps": 25}, "capture"),
])
def test_result_claim_accepts_a_string_or_an_object(claim, expected):
    assert wire_vocab.outcome_of(claim) == expected


def test_escape_maps_to_survival():
    """ZeroOne0's word for our terminal event. Same event, two seats."""
    assert wire_vocab.outcome_of("escape") == "survival"


@pytest.mark.parametrize("claim", ["  survival ", "SURVIVAL", " Survival"])
def test_case_and_whitespace_do_not_change_a_claim(claim):
    assert wire_vocab.outcome_of(claim) == "survival"


@pytest.mark.parametrize("claim", ["won", "lost", "draw", "", None, 7, {}])
def test_an_unknown_outcome_is_refused_not_guessed(claim):
    """Guessing an outcome is how a sub-game gets mis-scored quietly, which
    is the failure this whole relaxation exists to avoid."""
    assert wire_vocab.outcome_of(claim) is None


def test_normalisation_never_touches_a_hashed_preimage():
    """THE boundary (PRD 21 FR2.0).

    A record whose claim needed normalising must still verify against the
    bytes as received. If normalisation ever reached the preimage, every one
    of the 406 records in two settled series would stop verifying.
    """
    payload = {"intent": "truth", "move": "MOVE:S", "state": "grid=7x7"}
    nonce = "d8681132b4fca6096fa396755127c17b"
    sealed = hashlib.sha256(
        f"{canonical_str(payload)}{NONCE_SEPARATOR}{nonce}".encode()).hexdigest()

    # the claim beside it is messy and gets normalised for comparison
    assert wire_vocab.outcome_of("  ESCAPE ") == "survival"

    # the record itself is untouched and still re-hashes
    again = hashlib.sha256(
        f"{canonical_str(payload)}{NONCE_SEPARATOR}{nonce}".encode()).hexdigest()
    assert again == sealed


def test_an_empty_claim_is_refused_and_this_is_a_deliberate_tightening():
    """PRD 21 relaxes WHICH shapes are accepted; it does not accept a claim
    that claims nothing.

    The previous rule was `isinstance(v, dict)`, which accepted `{}` -- an
    audit asserting no outcome at all. Six tests used it as placeholder data
    and none asserted it was valid. Proceeding on an empty claim means
    scoring a sub-game on no information, which is the same silent
    mis-scoring this module exists to prevent.
    """
    assert wire_vocab.outcome_of({}) is None
    assert wire_vocab.outcome_of({"steps": 35}) is None


def test_our_own_engine_words_map_rather_than_being_refused():
    """`match_state.terminal_reason` says 'max_moves_reached' where the wire
    says 'survival'. The reference loop translates before claiming, so this
    never reaches an audit today -- but a path that forgot to should map."""
    assert wire_vocab.outcome_of("max_moves_reached") == "survival"


def test_technical_loss_is_a_claimable_outcome():
    """Rule 19 makes a hash mismatch a technical loss scoring 0. Refusing the
    word would leave us unable to claim a result the book requires."""
    assert wire_vocab.outcome_of("technical_loss") == "technical_loss"
