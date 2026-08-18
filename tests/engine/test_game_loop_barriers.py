"""The episode builds its board from the configured layout (PLAN.md §4.3).

``GameEpisode.reset`` is the single choke point: the trainer, each peer's
server and the off-manifold probe all construct episodes, so populating the
board here is what makes them agree without any of them knowing how a layout
is built.
"""

from dataclasses import replace

import pytest

from engine.barriers import barrier_layout
from engine.config import load_config
from engine.game_loop import GameEpisode


@pytest.fixture
def config():
    return replace(load_config("config/game.json"), barrier_seed=20260818)


def test_reset_populates_the_board_with_the_configured_layout(config):
    episode = GameEpisode(config)

    placed = {
        cell
        for cell in barrier_layout(config)
        if episode.board.is_barrier(cell)
    }
    assert placed == barrier_layout(config)
    assert episode.board.barrier_count == config.max_barriers


def test_a_second_reset_rebuilds_the_same_board(config):
    """Replaying an episode must not accumulate or drop barriers."""
    episode = GameEpisode(config)
    episode.reset()

    assert episode.board.barrier_count == config.max_barriers


def test_a_null_seed_still_yields_a_bare_board(config):
    """Pre-Phase-9 behaviour stays reachable by configuration alone."""
    episode = GameEpisode(replace(config, barrier_seed=None))

    assert episode.board.barrier_count == 0


def test_neither_agent_starts_inside_a_wall(config):
    episode = GameEpisode(config)

    assert not episode.board.is_barrier(episode.cop_state.position)
    assert not episode.board.is_barrier(episode.thief_state.position)
