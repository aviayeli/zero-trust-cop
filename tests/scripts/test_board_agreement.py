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




@pytest.fixture
def config():
    return load_config("config/game.json")


def test_agreeing_peers_pass(config, peer_stub):
    peers = [peer_stub(14), peer_stub(14, "thief")]

    asyncio.run(verify_board_agreement(peers, 14))

    assert all(peer.calls for peer in peers), "the board was never actually checked"


def test_a_peer_on_a_bare_board_is_refused(config, peer_stub):
    """The exact cross-group case: they omitted our optional extension."""
    peers = [peer_stub(14), peer_stub(0, "thief")]

    with pytest.raises(BoardMismatchError) as raised:
        asyncio.run(verify_board_agreement(peers, 14))

    assert "0" in str(raised.value) and "14" in str(raised.value)


def test_a_peer_disagreeing_with_OUR_board_is_refused(config, peer_stub):
    """Both peers may agree with each other and still not match our engine."""
    peers = [peer_stub(9), peer_stub(9, "thief")]

    with pytest.raises(BoardMismatchError):
        asyncio.run(verify_board_agreement(peers, 14))


def test_the_error_names_the_cause_not_just_the_symptom(peer_stub):
    peers = [peer_stub(14), peer_stub(0, "thief")]

    with pytest.raises(BoardMismatchError) as raised:
        asyncio.run(verify_board_agreement(peers, 14))

    assert "barrier" in str(raised.value).lower()


def test_each_peer_is_asked_about_its_OWN_role(peer_stub):
    """Asking the thief peer about the cop returns invalid_role, not a board."""
    peers = [peer_stub(14), peer_stub(14, "thief")]

    asyncio.run(verify_board_agreement(peers, 14))

    assert [peer.asked for peer in peers] == ["cop", "thief"]


def test_a_peer_on_a_different_axis_origin_is_refused(peer_stub):
    """A mirrored engine produces a plausible wrong game, not an error."""
    peers = [
        peer_stub(14, axis_origin_corner="topleft"),
        peer_stub(14, "thief", axis_origin_corner="bottomleft"),
    ]

    with pytest.raises(BoardMismatchError, match="axis_origin_corner"):
        asyncio.run(verify_board_agreement(peers, 14))


def test_a_peer_on_a_different_start_index_is_refused(peer_stub):
    peers = [peer_stub(14, axis_start_index=0), peer_stub(14, "thief", axis_start_index=1)]

    with pytest.raises(BoardMismatchError, match="axis_start_index"):
        asyncio.run(verify_board_agreement(peers, 14))


def test_a_peer_that_does_not_REPORT_the_axis_is_allowed(peer_stub):
    """Silence is not disagreement.

    These fields are an extension to the observation payload. A peer built
    before it existed reports no axis at all, and refusing it would repeat the
    `barrier_seed` mistake: turning an optional addition into a match we
    cannot play.
    """
    peers = [peer_stub(14), peer_stub(14, "thief")]

    asyncio.run(verify_board_agreement(peers, 14))


@pytest.mark.parametrize("spelling", ["top-left", "topleft"])
def test_matching_axis_fields_pass(peer_stub, spelling):
    """Both spellings name the SAME corner. The league writes `top-left`; we
    used to write `topleft`, and other teams still may. Refusing one of them
    rejects a peer that agrees with us, over a hyphen."""
    peers = [
        peer_stub(14, axis_origin_corner="topleft", axis_start_index=0),
        peer_stub(14, "thief", axis_origin_corner="topleft", axis_start_index=0),
    ]

    asyncio.run(verify_board_agreement(peers, 14))
