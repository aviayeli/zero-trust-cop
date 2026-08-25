"""Fixtures wiring the remote-loop fakes to a real board and config.

The doubles themselves live in ``tests/_support/remote_fakes`` — importable
because ``pythonpath`` names that directory, which a test package could not
be without colliding with the ``scripts`` package in ``src``.
"""

import anyio
import pytest
from remote_fakes import FakeClient, FakePeer

from engine.barriers import populated_board
from engine.config import load_config
from scripts.remote_match import play_remote_match

TURNS = 3


@pytest.fixture
def turns():
    return TURNS


@pytest.fixture
def config():
    return load_config("config/police/game.json")


@pytest.fixture
def board(config):
    return populated_board(config)


@pytest.fixture
def fake_client():
    return FakeClient


@pytest.fixture
def peers(config, board):
    """Our own running peer and the opponent's, scripted identically."""

    def build(own_engine, their_engine, **kwargs):
        return tuple(
            FakePeer(config, board, engine, TURNS, **kwargs)
            for engine in (own_engine, their_engine)
        )

    return build


@pytest.fixture
def play():
    """Run the loop with a poll interval short enough for a unit test."""

    def run(client, local, remote, board, config):
        return anyio.run(
            lambda: play_remote_match(
                client, local, remote, board, config, poll_interval_sec=0.001
            )
        )

    return run
