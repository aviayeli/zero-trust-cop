"""Peers must agree on the BOARD before they agree on moves (audit T-1).

A peer whose config omits `barrier_seed` plays a bare board while ours plays
fourteen barriers. Every turn then resolves differently and the match dies on
`DivergenceError` — a message about positions, for a fault that is really a
mismatched contract. Worse, it dies mid-match, after both peers have signed
commitments for a game that was never playable.

The board is observable before turn 0 (`get_observation` reports
`barrier_count`), so the disagreement is caught there and named for what it
is. This is the check that a loopback test cannot motivate and a cross-group
match would have failed on.
"""

import asyncio

import pytest

from engine.config import load_config
from scripts.board_agreement import BoardMismatchError, verify_board_agreement


class _Peer:
    """A connection stub reporting a fixed barrier count."""

    def __init__(self, barriers, own_role="cop", **extra):
        self.barriers = barriers
        self.own_role = own_role
        self.calls = 0
        self.asked = None
        self.extra = extra

    def __init_subclass__(cls):  # pragma: no cover - documentation only
        raise TypeError("stub is final")

    async def get_observation(self, role):
        self.calls += 1
        self.asked = role
        if role != self.own_role:
            return {"status": "error", "reason": "invalid_role"}
        return dict(
            {"role": role, "barrier_count": self.barriers, "grid_size": 7},
            **self.extra,
        )


@pytest.fixture
def config():
    return load_config("config/game.json")


def test_agreeing_peers_pass(config):
    peers = [_Peer(14), _Peer(14, "thief")]

    asyncio.run(verify_board_agreement(peers, 14))

    assert all(peer.calls for peer in peers), "the board was never actually checked"


def test_a_peer_on_a_bare_board_is_refused(config):
    """The exact cross-group case: they omitted our optional extension."""
    peers = [_Peer(14), _Peer(0, "thief")]

    with pytest.raises(BoardMismatchError) as raised:
        asyncio.run(verify_board_agreement(peers, 14))

    assert "0" in str(raised.value) and "14" in str(raised.value)


def test_a_peer_disagreeing_with_OUR_board_is_refused(config):
    """Both peers may agree with each other and still not match our engine."""
    peers = [_Peer(9), _Peer(9, "thief")]

    with pytest.raises(BoardMismatchError):
        asyncio.run(verify_board_agreement(peers, 14))


def test_the_error_names_the_cause_not_just_the_symptom():
    peers = [_Peer(14), _Peer(0, "thief")]

    with pytest.raises(BoardMismatchError) as raised:
        asyncio.run(verify_board_agreement(peers, 14))

    assert "barrier" in str(raised.value).lower()


def test_each_peer_is_asked_about_its_OWN_role():
    """Asking the thief peer about the cop returns invalid_role, not a board."""
    peers = [_Peer(14), _Peer(14, "thief")]

    asyncio.run(verify_board_agreement(peers, 14))

    assert [peer.asked for peer in peers] == ["cop", "thief"]


def test_a_peer_on_a_different_axis_origin_is_refused():
    """A mirrored engine produces a plausible wrong game, not an error."""
    peers = [
        _Peer(14, axis_origin_corner="topleft"),
        _Peer(14, "thief", axis_origin_corner="bottomleft"),
    ]

    with pytest.raises(BoardMismatchError, match="axis_origin_corner"):
        asyncio.run(verify_board_agreement(peers, 14))


def test_a_peer_on_a_different_start_index_is_refused():
    peers = [_Peer(14, axis_start_index=0), _Peer(14, "thief", axis_start_index=1)]

    with pytest.raises(BoardMismatchError, match="axis_start_index"):
        asyncio.run(verify_board_agreement(peers, 14))


def test_a_peer_that_does_not_REPORT_the_axis_is_allowed():
    """Silence is not disagreement.

    These fields are an extension to the observation payload. A peer built
    before it existed reports no axis at all, and refusing it would repeat the
    `barrier_seed` mistake: turning an optional addition into a match we
    cannot play.
    """
    peers = [_Peer(14), _Peer(14, "thief")]

    asyncio.run(verify_board_agreement(peers, 14))


def test_matching_axis_fields_pass():
    peers = [
        _Peer(14, axis_origin_corner="topleft", axis_start_index=0),
        _Peer(14, "thief", axis_origin_corner="topleft", axis_start_index=0),
    ]

    asyncio.run(verify_board_agreement(peers, 14))
