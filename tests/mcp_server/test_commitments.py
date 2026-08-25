"""Contract tests for the per-turn commitment/reveal ordering rules."""

from mcp_server.commitments import CommitmentBook
from mcp_server.crypto import commit

STATE = "turn-state"
INTENT = "move"


def _commit(move: str):
    return commit(STATE, move, INTENT)


def test_first_commit_is_half_and_second_is_both_committed():
    book = CommitmentBook()
    police_hash, _ = _commit("N")
    thief_hash, _ = _commit("S")

    assert book.commit("police", 0, police_hash).status == "waiting"
    assert book.state() == "half"
    assert book.commit("thief", 0, thief_hash).status == "both_committed"
    assert book.state() == "both_committed"


def test_second_commit_by_same_role_is_rejected_without_overwriting_first():
    book = CommitmentBook()
    original_hash, original_nonce = _commit("N")
    replacement_hash, _ = _commit("S")
    thief_hash, thief_nonce = _commit("E")

    book.commit("police", 0, original_hash)
    outcome = book.commit("police", 0, replacement_hash)
    assert outcome.status == "rejected"
    assert outcome.reason == "already_committed"
    book.commit("thief", 0, thief_hash)

    assert book.reveal("police", 0, STATE, "N", INTENT, original_nonce).status == "waiting"
    assert book.reveal("thief", 0, STATE, "E", INTENT, thief_nonce).status == "resolved"


def test_reveal_before_both_commitments_is_rejected_to_prevent_front_running():
    """A peer must not reveal until both commitments are in, preventing front-running."""
    book = CommitmentBook()
    police_hash, police_nonce = _commit("N")
    book.commit("police", 0, police_hash)

    outcome = book.reveal("police", 0, STATE, "N", INTENT, police_nonce)

    assert outcome.status == "rejected"
    assert outcome.reason == "reveal_before_commit"


def test_reveal_that_does_not_match_stored_commitment_is_rejected():
    book = CommitmentBook()
    police_hash, police_nonce = _commit("N")
    thief_hash, _ = _commit("S")
    book.commit("police", 0, police_hash)
    book.commit("thief", 0, thief_hash)

    outcome = book.reveal("police", 0, STATE, "S", INTENT, police_nonce)

    assert outcome.status == "rejected"
    assert outcome.reason == "broken_commitment"


def test_both_valid_reveals_resolve_with_each_role_move_once():
    book = CommitmentBook()
    police_hash, police_nonce = _commit("N")
    thief_hash, thief_nonce = _commit("S")
    book.commit("police", 0, police_hash)
    book.commit("thief", 0, thief_hash)

    assert book.reveal("police", 0, STATE, "N", INTENT, police_nonce).status == "waiting"
    outcome = book.reveal("thief", 0, STATE, "S", INTENT, thief_nonce)

    assert outcome.status == "resolved"
    assert outcome.moves == {"police": "N", "thief": "S"}
    assert book.state() == "resolved"


def test_later_turn_resets_slots_and_earlier_turn_operations_are_stale():
    book = CommitmentBook()
    old_hash, old_nonce = _commit("N")
    new_hash, _ = _commit("S")
    book.commit("police", 0, old_hash)

    assert book.commit("thief", 1, new_hash).status == "waiting"
    assert book.state() == "half"
    assert book.commit("police", 0, old_hash).reason == "stale_turn"
    assert book.reveal("police", 0, STATE, "N", INTENT, old_nonce).reason == "stale_turn"


def test_unknown_role_is_rejected_for_commit_and_reveal():
    book = CommitmentBook()
    h_commit, nonce = _commit("N")

    assert book.commit("spectator", 0, h_commit).reason == "invalid_role"
    assert book.reveal("spectator", 0, STATE, "N", INTENT, nonce).reason == "invalid_role"


def test_revealing_twice_for_the_same_role_is_rejected():
    book = CommitmentBook()
    police_hash, police_nonce = _commit("N")
    thief_hash, _ = _commit("S")
    book.commit("police", 0, police_hash)
    book.commit("thief", 0, thief_hash)
    book.reveal("police", 0, STATE, "N", INTENT, police_nonce)

    outcome = book.reveal("police", 0, STATE, "N", INTENT, police_nonce)

    assert outcome.status == "rejected"
    assert outcome.reason == "already_revealed"


def test_commitment_for_returns_the_stored_digest_for_a_role():
    book = CommitmentBook()
    h_commit, _ = _commit("N")

    assert book.commitment_for("police") is None
    book.commit("police", 0, h_commit)
    assert book.commitment_for("police") == h_commit


def test_reveal_for_a_future_turn_is_rejected_rather_than_read_against_this_turn():
    """A reveal must not be checked against a PREVIOUS turn's stored digest.

    ``commit`` resets the book when the turn advances; ``reveal`` only guarded
    the stale direction, so a future-turn reveal fell through to the current
    turn's commitments. ``SubmissionGate`` rejects the mismatch first, so this
    is defence in depth on a reusable primitive, not a live hole.
    """
    book = CommitmentBook()
    police_hash, police_nonce = _commit("N")
    thief_hash, _ = _commit("S")
    book.commit("police", 0, police_hash)
    book.commit("thief", 0, thief_hash)

    outcome = book.reveal("police", 1, STATE, "N", INTENT, police_nonce)

    assert outcome.status == "rejected"
    assert outcome.reason == "future_turn"
    assert book.state() == "both_committed"
