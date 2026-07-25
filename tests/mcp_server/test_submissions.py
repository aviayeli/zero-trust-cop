"""Contract tests for the authenticated peer-submission pipeline."""

import asyncio

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from engine.config import load_config
from engine.game_loop import GameEpisode
from mcp_server.commitments import CommitmentBook
from mcp_server.crypto import commit
from mcp_server.identity import sign
from mcp_server.match_state import MatchState
from mcp_server.submissions import SubmissionGate


def _gate():
    keys = {role: Ed25519PrivateKey.generate() for role in ("police", "thief")}
    config = load_config("config/game.json")
    state = MatchState(GameEpisode(config), config.response_timeout_sec)
    return SubmissionGate(state, CommitmentBook(),
                          {role: key.public_key() for role, key in keys.items()},
                          {"police": "cop", "thief": "thief"}), state, keys


def _signed(key, role, turn, digest):
    return sign(key, role, turn, digest)


def _commitment(key, role, turn, move="N"):
    digest, nonce = commit("state", move, "move")
    return digest, nonce, _signed(key, role, turn, digest)


def test_signed_commitment_is_accepted():
    gate, _, keys = _gate()
    digest, _, signature = _commitment(keys["police"], "police", 0)
    assert gate.submit_commitment("police", 0, digest, signature)["status"] == "waiting"


def test_wrong_key_rejects_without_storing_commitment():
    gate, _, keys = _gate()
    digest, _, signature = _commitment(keys["thief"], "police", 0)
    assert gate.submit_commitment("police", 0, digest, signature)["error"] == "invalid_signature"
    assert gate.book.commitment_for("police") is None


def test_tampered_digest_rejects_without_storing_commitment():
    gate, _, keys = _gate()
    digest, _, signature = _commitment(keys["police"], "police", 0)
    assert gate.submit_commitment("police", 0, "0" * 64, signature)["error"] == "invalid_signature"
    assert gate.book.commitment_for("police") is None


@pytest.mark.parametrize("turn", [-1, 1])
def test_turn_authority_rejects_lower_and_higher_turn_before_book_mutation(turn):
    gate, _, keys = _gate()
    digest, _, signature = _commitment(keys["police"], "police", turn)
    assert gate.submit_commitment("police", turn, digest, signature)["error"] == "wrong_turn"
    assert gate.book.commitment_for("police") is None


def test_signature_replayed_at_next_turn_is_rejected_by_pipeline():
    gate, state, keys = _gate()
    digest, _, signature = _commitment(keys["police"], "police", 0)

    async def advance_turn():
        await state.submit("cop", "N")
        await state.submit("thief", "S")

    asyncio.run(advance_turn())
    assert gate.submit_commitment("police", 1, digest, signature)["error"] == "invalid_signature"


def test_reveal_before_both_commits_is_rejected():
    gate, _, keys = _gate()
    digest, nonce, signature = _commitment(keys["police"], "police", 0)
    gate.submit_commitment("police", 0, digest, signature)
    assert asyncio.run(gate.reveal_move("police", 0, "state", "N", "move", nonce, signature))["error"] == "reveal_before_commit"


@pytest.mark.parametrize("move, signature_key", [("S", "police"), ("N", "thief")])
def test_broken_commitment_and_bad_reveal_signature_are_rejected(move, signature_key):
    gate, _, keys = _gate()
    police_digest, police_nonce, police_signature = _commitment(keys["police"], "police", 0)
    thief_digest, _, thief_signature = _commitment(keys["thief"], "thief", 0, "S")
    gate.submit_commitment("police", 0, police_digest, police_signature)
    gate.submit_commitment("thief", 0, thief_digest, thief_signature)
    signature = _signed(keys[signature_key], "police", 0, police_digest)
    expected = "broken_commitment" if move == "S" else "invalid_signature"
    result = asyncio.run(gate.reveal_move("police", 0, "state", move, "move", police_nonce, signature))
    assert result["error"] == expected


def test_signed_reveals_resolve_once_and_advance_one_turn():
    gate, state, keys = _gate()
    police = _commitment(keys["police"], "police", 0, "N")
    thief = _commitment(keys["thief"], "thief", 0, "S")
    gate.submit_commitment("police", 0, police[0], police[2])
    gate.submit_commitment("thief", 0, thief[0], thief[2])

    async def reveal_both():
        first = await gate.reveal_move("police", 0, "state", "N", "move", police[1], police[2])
        second = await gate.reveal_move("thief", 0, "state", "S", "move", thief[1], thief[2])
        return first, second

    first, second = asyncio.run(reveal_both())
    assert first["status"] == "waiting" and second["status"] == "resolved"
    assert state.turn_count == 1


def test_all_rejections_have_the_standard_error_shape():
    gate, _, _ = _gate()
    result = gate.submit_commitment("spectator", 0, "digest", "signature")
    assert set(result) == {"error", "message"}


def test_unknown_role_is_rejected_by_both_entry_points():
    gate, _, keys = _gate()
    digest, _, signature = _commitment(keys["police"], "spectator", 0)
    assert gate.submit_commitment("spectator", 0, digest, signature)["error"] == "invalid_role"
    result = asyncio.run(gate.reveal_move("spectator", 0, "state", "N", "move", "nonce", signature))
    assert result["error"] == "invalid_role"
