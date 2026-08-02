"""The real transport: two peer PROCESSES talking streamable HTTP (D1).

Slower than the in-process tests by design. Without these, the exchange logic
could be perfect while the servers never actually spoke to each other — the
"verified but unwired" failure this whole phase exists to close.

Everything runs against an ISOLATED config root under tmp_path, never the real
``config/``. An earlier version of this file called ``ensure_keys()`` with no
argument; a mutation run that disabled the idempotency guard then regenerated
the PRODUCTION signing keys — key material that is gitignored and therefore
unrecoverable. A test must never be able to reach it.
"""

from random import Random

import anyio
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from engine.board import Board
from engine.config import load_config
from mcp_server.http_peer import HttpPeer
from mcp_server.identity import load_signing_key
from mcp_server.keygen import ensure_keys
from mcp_server.peer_client import PeerClient
from mcp_server.peer_policy import build_peer_policy
from scripts.peer_processes import port_is_open, running_peers
from scripts.run_local_mcp_match import connected_peers, peer_url, run_match


@pytest.fixture
def isolated_root(secure_config_root):
    """A complete peer workspace with its own throwaway signing keys."""
    ensure_keys(secure_config_root)
    return secure_config_root


@pytest.fixture
def match_config(isolated_root):
    return load_config(f"{isolated_root}/police/game.json")


def test_a_failing_block_still_stops_both_peers(isolated_root):
    """A crashed match must never leave a listener bound to its port."""
    bindings = {}

    with pytest.raises(RuntimeError):
        with running_peers(isolated_root) as started:
            bindings.update(started)
            assert port_is_open(started["police"].host, started["police"].port)
            raise RuntimeError("match blew up")

    for binding in bindings.values():
        assert not port_is_open(binding.host, binding.port, timeout=0.5)


def test_both_peers_answer_over_http(isolated_root):
    with running_peers(isolated_root) as bindings:

        async def ask():
            async with connected_peers(bindings) as connections:
                return [await peer.get_match_status() for peer in connections]

        statuses = anyio.run(ask)

    assert len(statuses) == 2
    for status in statuses:
        assert status["turn_count"] == 0
        assert status["is_terminated"] is False


def test_a_full_match_plays_over_the_wire(isolated_root, match_config):
    with running_peers(isolated_root) as bindings:
        history = anyio.run(run_match, bindings, match_config, 20260801, isolated_root)

    assert history
    final = history[-1]["result"]
    assert final["is_terminated"] is True
    assert final["terminal_reason"] in {"capture", "max_moves_reached"}


def test_a_tampered_reveal_is_refused_over_the_wire(isolated_root, match_config):
    """The security is live in the RUNNING server, not merely unit-tested."""

    async def tamper(bindings):
        url = peer_url(bindings["police"])
        async with streamable_http_client(url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                peer = HttpPeer(session)
                board = Board(match_config)
                submissions = {
                    role: PeerClient(
                        role,
                        build_peer_policy(role, engine, match_config, isolated_root),
                        load_signing_key(role, isolated_root),
                        Random(3),
                    ).prepare(0, (0, 0), (3, 3), board)
                    for role, engine in (("police", "cop"), ("thief", "thief"))
                }
                for entry in submissions.values():
                    await peer.submit_commitment(
                        entry.role, 0, entry.h_commit, entry.signature
                    )
                police = submissions["police"]
                swapped = "south" if police.move != "south" else "north"
                return await peer.reveal_move(
                    "police", 0, police.state, swapped,
                    police.intent, police.nonce, police.signature,
                )

    with running_peers(isolated_root) as bindings:
        outcome = anyio.run(tamper, bindings)

    assert outcome["error"] == "broken_commitment"
