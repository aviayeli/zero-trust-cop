"""Tests for the public canonical JSON wire-format helper."""

import hashlib

from mcp_server.crypto import canonical_json


def test_canonical_json_sorts_keys_without_whitespace():
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_canonical_json_returns_bytes():
    assert isinstance(canonical_json({"a": 1}), bytes)


def test_canonical_json_ignores_key_insertion_order():
    assert canonical_json({"a": 1, "b": 2}) == canonical_json({"b": 2, "a": 1})


def test_canonical_json_preserves_commit_reveal_wire_format():
    payload = {
        "state": "turn-1",
        "move": "N",
        "intent": "probe",
        "nonce": "0" * 32,
    }
    encoded = canonical_json(payload)
    assert encoded == (
        b'{"intent":"probe","move":"N","nonce":"00000000000000000000000000000000",'
        b'"state":"turn-1"}'
    )
    assert hashlib.sha256(encoded).hexdigest() == (
        "9d991c9040ff8dc5a6616d6fb1c4a6e73e933c3eb0853dbd37c025a6991b345e"
    )
