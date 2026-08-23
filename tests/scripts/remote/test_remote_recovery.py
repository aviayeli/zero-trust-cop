"""Recovering a turn the wire never reported, and refusing to play on.

``SubmissionGate.reveal_move`` answers ``resolved`` only to the SECOND
revealer. When ours lands first the gate tells us nothing about the turn,
so the outcome has to be polled for and reassembled — and every way that
recovery can legitimately fail has to end the match rather than guess.
"""

from dataclasses import replace

import pytest

from mcp_server.http_peer import TechnicalLossError
from scripts.match_loop import DivergenceError
from scripts.remote_match import RemoteMatchError

def test_a_waiting_reveal_is_recovered_by_polling(peers, fake_client, board, config, play, turns):
    """Our reveal landed first, so the gate told us nothing about the turn."""
    local, remote = peers("cop", "thief", resolves_inline=False)

    history = play(fake_client("police"), local, remote, board, config)

    assert len(history) == turns
    assert local.status_polls > 0, "the loop never polled for the turn result"
    assert history[-1]["result"]["is_terminated"] is True


def test_the_polled_result_reassembles_both_positions(peers, fake_client, board, config, play, turns):
    """Each peer states only its OWN position (FR3), so the pair is rebuilt."""
    local, remote = peers("cop", "thief", resolves_inline=False)

    history = play(fake_client("police"), local, remote, board, config)

    first = history[0]["result"]
    assert tuple(first["cop_position"]) == tuple(config.cop_start)
    assert tuple(first["thief_position"]) != tuple(config.thief_start)


def test_history_records_only_the_submission_we_hold(peers, fake_client, board, config, play, turns):
    """We never see the opponent's nonce, so the log must not invent one."""
    local, remote = peers("cop", "thief", resolves_inline=True)

    history = play(fake_client("police"), local, remote, board, config)

    for entry in history:
        assert [item.role for item in entry["submissions"]] == ["police"]


def test_the_thief_side_plays_the_same_loop(peers, fake_client, board, config, play, turns):
    """The loop is role-agnostic; only the engine-role mapping differs."""
    local, remote = peers("thief", "cop", resolves_inline=True)

    history = play(fake_client("thief"), local, remote, board, config)

    assert len(history) == turns
    for peer in (local, remote):
        assert {role for role, *_ in peer.reveals} == {"thief"}


def test_peers_disagreeing_about_the_turn_are_a_divergence(peers, fake_client, board, config, play, turns):
    """Two engines reporting different states is what D2 exists to catch."""
    local, remote = peers("cop", "thief", resolves_inline=False)
    remote.turn_offset = 5

    with pytest.raises(DivergenceError):
        play(fake_client("police"), local, remote, board, config)


def test_a_peer_that_never_advances_forfeits(peers, fake_client, board, config, play, turns):
    """A silent opponent is a technical loss, not an unbounded wait."""
    local, remote = peers("cop", "thief", resolves_inline=False, stalled=True)
    impatient = replace(config, watchdog_timeout_sec=0.05)

    with pytest.raises(TechnicalLossError):
        play(fake_client("police"), local, remote, board, impatient)


def test_a_refused_submission_stops_the_match(peers, fake_client, board, config, play, turns):
    """A rejected commitment means the peers are out of step; do not play on."""
    local, remote = peers("cop", "thief", resolves_inline=True)
    remote.refuse_with = "wrong_turn"

    with pytest.raises(RemoteMatchError, match="wrong_turn"):
        play(fake_client("police"), local, remote, board, config)


def test_a_reveal_waits_for_the_opponents_commitment(
    peers, fake_client, board, config, play, turns
):
    """A peer refuses EVERY reveal until BOTH commitments are in.

    ``commitments.py`` enforces that as the anti-front-running rule, and the
    local runner never trips it because it pushes both commitments itself.
    Remotely we hold only our own half, so ``reveal_before_commit`` means
    'not yet' — retrying is the protocol, not a workaround.
    """
    local, remote = peers("cop", "thief", resolves_inline=True, commit_lag=2)

    history = play(fake_client("police"), local, remote, board, config)

    assert len(history) == turns
    assert local.refused_reveals == 2 * turns
    assert remote.refused_reveals == 2 * turns


def test_a_reveal_the_opponent_never_unblocks_forfeits(
    peers, fake_client, board, config, play, turns
):
    """Waiting for a commitment that never comes is still a technical loss."""
    local, remote = peers("cop", "thief", resolves_inline=True, commit_lag=10**6)
    impatient = replace(config, watchdog_timeout_sec=0.05)

    with pytest.raises(TechnicalLossError):
        play(fake_client("police"), local, remote, board, impatient)
