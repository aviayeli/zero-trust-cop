"""One peer's CLIENT side: decide, truncate, commit, sign.

The truncation ordering matters and is easy to get backwards: the digest must
cover the TRUNCATED intent, so a peer cannot commit to a long intent and then
reveal a short one (or the reverse) and still satisfy the commitment.
"""

from dataclasses import replace
from random import Random

import pytest

from engine.barriers import populated_board
from mcp_server.crypto import verify
from mcp_server.identity import verify_signature
from mcp_server.peer_client import PeerClient, state_token
from mcp_server.peer_policy import build_peer_policy


@pytest.fixture
def board(app):
    """A real Board: state_key scans it for barriers."""
    return populated_board(app.config)


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


def test_truncation_cannot_forge_a_lie(
    secure_config_root, peer_keys, app, board
):
    """A zero-word hint cap must not make an honest peer look deceptive.

    Under payload v3.0.0 the hint is no longer hashed — intent carries the
    honesty flag instead. Deriving that flag from the TRUNCATED hint would
    read an emptied string as disagreement and label a truthful cop a liar,
    so it is derived from the policy's untruncated claim.
    """
    policy = build_peer_policy("police", "cop", app.config, secure_config_root)
    policy.settings = replace(policy.settings, hint_max_words=0)
    client = PeerClient("police", policy, peer_keys["police"], Random(1))

    submission = _prepare(client, board)

    assert submission.intent == "truth", "an honest cop must stay 'truth'"
    assert verify(
        submission.state, submission.move, submission.intent,
        submission.nonce, submission.h_commit,
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
