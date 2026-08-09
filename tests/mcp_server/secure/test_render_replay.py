"""Step-by-step ASCII rendering of a replay (--render).

Rendering is a VIEW over the same replay the verifier performs: it steps a
fresh GameEpisode from the logged moves, so what is drawn is what actually
reconstructs — not the positions the log claims.

Nothing here sleeps. The pause is injected, exactly as the match clock is.
"""

import json
from pathlib import Path

import pytest

from engine.config import load_config
from mcp_server.peer_keys import load_public_keys
from scripts.heatmap import EMPTY, heat_cell, scent_symbol
from scripts.render_replay import (
    BARRIER,
    CAPTURE,
    COP,
    THIEF,
    board_lines,
    render_replay,
    replay_frames,
    turn_checks,
)

REAL_LOG = Path("logs/aviayeli/log_aviayeli_g01.json")


@pytest.fixture
def config():
    return load_config("config/game.json")


@pytest.fixture
def real_log():
    return json.loads(REAL_LOG.read_text())


@pytest.fixture
def public_keys():
    return load_public_keys("police")


def test_an_untouched_cell_shows_as_empty():
    assert scent_symbol(0.0) == EMPTY


def test_a_faint_trace_shows_the_lowest_level():
    assert scent_symbol(0.01) == "1"


def test_a_strong_trace_shows_a_higher_level_than_a_faint_one():
    assert scent_symbol(0.9) > scent_symbol(0.1)


def test_scent_never_exceeds_the_top_level():
    assert scent_symbol(99.0) == "9"


def test_the_board_is_square_and_the_configured_size(config):
    lines = board_lines(config, (0, 0), (3, 3), frozenset(), {})

    assert len(lines) == config.grid_size
    for line in lines:
        assert len(line.split()) == config.grid_size


def test_the_agents_and_barriers_are_drawn(config):
    lines = board_lines(config, (0, 0), (3, 3), frozenset({(1, 1)}), {})
    cells = [line.split() for line in lines]

    assert cells[0][0] == COP
    assert cells[3][3] == THIEF
    assert cells[1][1] == BARRIER


def test_a_shared_cell_is_drawn_as_a_capture(config):
    cells = [line.split() for line in board_lines(config, (2, 2), (2, 2), frozenset(), {})]

    assert cells[2][2] == CAPTURE


def test_scent_is_drawn_on_visited_cells(config):
    cells = [
        line.split()
        for line in board_lines(config, (0, 0), (6, 6), frozenset(), {(4, 4): 0.9})
    ]

    assert cells[4][4] == "9"


def test_an_agent_outranks_a_scent_trace_on_the_same_cell(config):
    """A trace must never hide where an agent actually is."""
    cells = [
        line.split()
        for line in board_lines(config, (0, 0), (3, 3), frozenset(), {(0, 0): 0.9})
    ]

    assert cells[0][0] == COP


def test_a_strong_belief_is_a_brighter_red_than_a_faint_one():
    """The heatmap shades in PROPORTION to belief, not a flat mark."""
    faint = heat_cell(0.05, colour=True)
    strong = heat_cell(0.95, colour=True)

    assert faint != strong
    assert "\033[38;5;" in faint and "\033[38;5;" in strong


def test_an_empty_cell_is_never_shaded():
    assert heat_cell(0.0, colour=True) == EMPTY


def test_the_heatmap_stays_byte_clean_without_colour():
    assert heat_cell(0.9, colour=False) == scent_symbol(0.9)
    assert "\033" not in heat_cell(0.9, colour=False)
