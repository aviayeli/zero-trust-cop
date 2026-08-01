"""One peer's CLIENT side: decide, truncate, commit, sign.

The truncation ordering matters and is easy to get backwards: the digest must
cover the TRUNCATED intent, so a peer cannot commit to a long intent and then
reveal a short one (or the reverse) and still satisfy the commitment.
"""

from dataclasses import replace
from random import Random

import pytest

from engine.board import Board
from mcp_server.crypto import verify
from mcp_server.identity import verify_signature
from mcp_server.peer_client import PeerClient, state_token
from mcp_server.peer_policy import build_peer_policy


@pytest.fixture
def board(app):
    """A real Board: state_key scans it for barriers."""
    return Board(app.config)


@pytest.fixture
def client(app, peer_keys):
    return PeerClient("police", app.policy, peer_keys["police"], Random(1))


def _prepare(client, board, turn=0):
    return client.prepare(turn, (0, 0), (3, 3), board)


def test_a_submission_carries_everything_a_reveal_needs(client, board):
    submission = _prepare(client, board)

    assert submission.role == "police"
    assert submission.turn == 0
    assert submission.h_commit and submission.signature
    assert submission.nonce and submission.move


def test_the_digest_covers_exactly_what_will_be_revealed(client, board):
    submission = _prepare(client, board)

    assert verify(
        submission.state,
        submission.move,
        submission.intent,
        submission.nonce,
        submission.h_commit,
    )


def test_the_signature_authenticates_the_commitment(client, board, peer_keys):
    submission = _prepare(client, board, turn=4)

    assert verify_signature(
        peer_keys["police"].public_key(),
        "police",
        4,
        submission.h_commit,
        submission.signature,
    )


def test_the_signature_does_not_carry_to_another_turn(client, board, peer_keys):
    submission = _prepare(client, board, turn=4)

    assert not verify_signature(
        peer_keys["police"].public_key(),
        "police",
        5,
        submission.h_commit,
        submission.signature,
    )


def test_the_committed_intent_respects_the_configured_word_cap(client, board, app):
    submission = _prepare(client, board)

    cap = app.policy.settings.hint_max_words
    assert len(submission.intent.split()) <= cap


def test_truncation_happens_BEFORE_the_digest_is_computed(
    secure_config_root, peer_keys, app, board
):
    """Proved with a zero-word cap, so the cap cannot pass vacuously.

    Real intents are a single direction word, well under the configured cap of
    15, so a cap assertion alone would hold even if truncation were applied
    after committing — or never applied at all.
    """
    policy = build_peer_policy("police", "cop", app.config, secure_config_root)
    policy.settings = replace(policy.settings, hint_max_words=0)
    client = PeerClient("police", policy, peer_keys["police"], Random(1))

    submission = _prepare(client, board)

    assert submission.intent == ""
    assert verify(
        submission.state, submission.move, "", submission.nonce, submission.h_commit
    )


def test_a_seeded_client_is_deterministic(app, board, peer_keys):
    first = PeerClient("police", app.policy, peer_keys["police"], Random(7))
    second = PeerClient("police", app.policy, peer_keys["police"], Random(7))

    assert _prepare(first, board).move == _prepare(second, board).move


def test_the_state_token_binds_the_turn_and_both_positions():
    token = state_token(3, (0, 1), (2, 2))

    assert token != state_token(4, (0, 1), (2, 2))
    assert token != state_token(3, (0, 2), (2, 2))
    assert token != state_token(3, (0, 1), (2, 3))
