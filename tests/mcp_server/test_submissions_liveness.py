"""Liveness and peer-vocabulary regression tests for submission handling."""

import asyncio

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
    gate = SubmissionGate(state, CommitmentBook(),
                          {role: key.public_key() for role, key in keys.items()},
                          {"police": "cop", "thief": "thief"})
    return gate, state, keys


def _submission(keys, role, move):
    digest, nonce = commit("state", move, "truth")
    return digest, nonce, sign(keys[role], role, 0, digest)


def test_invalid_reveal_leaves_book_and_engine_live():
    gate, state, keys = _gate()
    police, thief = _submission(keys, "police", "DIAGONAL"), _submission(keys, "thief", "south")
    gate.submit_commitment("police", 0, police[0], police[2])
    gate.submit_commitment("thief", 0, thief[0], thief[2])
    result = asyncio.run(gate.reveal_move("police", 0, "state", "DIAGONAL", "truth", police[1], police[2]))
    assert result["error"] == "invalid_direction"
    assert gate.book.state() == "both_committed" and state.turn_count == 0
    assert asyncio.run(gate.reveal_move("thief", 0, "state", "south", "truth", thief[1], thief[2]))["status"] == "waiting"


def test_commitment_waiting_payload_uses_peer_roles():
    gate, _, keys = _gate()
    police = _submission(keys, "police", "north")
    result = gate.submit_commitment("police", 0, police[0], police[2])
    assert result["role"] == "police" and result["message"].endswith("thief")


def test_resolved_payload_uses_revealing_peer_role():
    gate, _, keys = _gate()
    police, thief = _submission(keys, "police", "north"), _submission(keys, "thief", "south")
    gate.submit_commitment("police", 0, police[0], police[2])
    gate.submit_commitment("thief", 0, thief[0], thief[2])
    asyncio.run(gate.reveal_move("thief", 0, "state", "south", "truth", thief[1], thief[2]))
    result = asyncio.run(gate.reveal_move("police", 0, "state", "north", "truth", police[1], police[2]))
    assert result["role"] == "police"
