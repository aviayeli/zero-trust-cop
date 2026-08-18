"""A full two-peer match, driven through the authenticated surface.

These run the peers IN-PROCESS: the app namespace already exposes exactly the
tool callables a remote connection presents, so the exchange logic is
transport-agnostic and can be exercised without spawning listeners. The real
HTTP transport is covered separately in test_http_match.py.
"""

import asyncio
from random import Random

import pytest

from engine.barriers import populated_board
from mcp_server.peer_client import PeerClient
from mcp_server.server import create_app
from scripts.match_loop import (
    DivergenceError,
    divergence,
    exchange_turn,
    play_match,
)


@pytest.fixture
def peers(secure_config_root, peer_keys):
    """Two real peers plus their clients, sharing one config root."""
    apps = {
        role: create_app(role, config_root=secure_config_root)
        for role in ("police", "thief")
    }
    clients = {
        role: PeerClient(role, apps[role].policy, peer_keys[role], Random(11))
        for role in ("police", "thief")
    }
    return apps, clients


def test_every_commitment_precedes_every_reveal(peers):
    """Ordering is the anti-front-running property, so assert the ORDER."""
    apps, clients = peers
    board = populated_board(apps["police"].config)
    calls = []

    class _Recorder:
        def __init__(self, inner):
            self._inner = inner

        async def submit_commitment(self, *args):
            calls.append("commit")
            return await self._inner.submit_commitment(*args)

        async def reveal_move(self, *args):
            calls.append("reveal")
            return await self._inner.reveal_move(*args)

    submissions = [
        clients[role].prepare(0, (0, 0), (3, 3), board)
        for role in ("police", "thief")
    ]
    connections = [_Recorder(apps[role]) for role in ("police", "thief")]

    asyncio.run(exchange_turn(0, submissions, connections))

    assert calls == ["commit"] * 4 + ["reveal"] * 4


def test_a_full_match_runs_to_termination_on_both_peers(peers):
    apps, clients = peers
    board = populated_board(apps["police"].config)
    connections = [apps["police"], apps["thief"]]

    history = asyncio.run(play_match(clients, connections, board, apps["police"].config))

    assert history
    assert history[-1]["result"]["is_terminated"] is True
    assert history[-1]["result"]["terminal_reason"] in {"capture", "max_moves_reached"}
    assert apps["police"].match_state.turn_count == apps["thief"].match_state.turn_count


def test_both_engines_agree_on_every_turn_of_a_real_match(peers):
    apps, clients = peers
    board = populated_board(apps["police"].config)

    history = asyncio.run(
        play_match(clients, [apps["police"], apps["thief"]], board, apps["police"].config)
    )

    assert apps["police"].match_state.cop_position == apps["thief"].match_state.cop_position
    assert len(history) == apps["police"].match_state.turn_count


def test_a_desynchronised_peer_is_DETECTED_not_absorbed(peers):
    """Mirrored local truth is only worth anything if divergence is caught."""
    apps, clients = peers
    board = populated_board(apps["police"].config)

    async def desync_then_play():
        # Advance the thief's engine alone, behind the protocol's back.
        await apps["thief"].match_state.submit("cop", "S")
        await apps["thief"].match_state.submit("thief", "N")
        return await play_match(
            clients, [apps["police"], apps["thief"]], board, apps["police"].config
        )

    with pytest.raises((DivergenceError, RuntimeError)):
        asyncio.run(desync_then_play())


def test_play_match_raises_when_two_peers_genuinely_disagree(peers):
    """DivergenceError must be a REACHABLE path, not decorative.

    Natural desync trips the wrong_turn guard first and surfaces as a
    RuntimeError, so the disagreement branch is forced here with a peer that
    resolves normally but reports a different board.
    """
    apps, clients = peers
    board = populated_board(apps["police"].config)

    class _LiesAboutPosition:
        def __init__(self, inner):
            self._inner = inner

        async def get_observation(self, role):
            # Passed through: this peer lies about POSITIONS mid-match, not
            # about the board, so it must clear the pre-match board check
            # (scripts/board_agreement.py) to reach the divergence it tests.
            return await self._inner.get_observation(role)

        async def submit_commitment(self, *args):
            return await self._inner.submit_commitment(*args)

        async def reveal_move(self, *args):
            outcome = await self._inner.reveal_move(*args)
            if outcome.get("status") == "resolved":
                return dict(outcome, thief_position=(6, 6))
            return outcome

    connections = [apps["police"], _LiesAboutPosition(apps["thief"])]

    with pytest.raises(DivergenceError) as raised:
        asyncio.run(play_match(clients, connections, board, apps["police"].config))

    assert "thief_position" in str(raised.value)
