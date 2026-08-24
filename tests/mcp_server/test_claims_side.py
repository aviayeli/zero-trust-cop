"""Our own piece on the reference-v3 wire (PRD_10 FR3-FR5).

The model this pins is the one the wire forces: we resolve OUR piece and we
do not know where theirs is. What this module covers is that piece — where it
starts, how it walks when a move is refused, and what it discloses about
itself every turn.

BOTH peers disclose. A cop that emitted `{}` would be silent about itself and
fully informed about them, which across a six-sub-game series with the sides
swapping is an advantage no rule grants it.

What ENDS a sub-game is pinned next door, in `test_claims_answers.py`.
"""

import pytest

from engine.board import Board
from engine.config import load_config
from mcp_server.claims_side import Side


@pytest.fixture
def config():
    return load_config("config/game.json")


@pytest.fixture
def board(config):
    return Board(config)


def _police(config, board):
    return Side(config, board, "police")


def _thief(config, board):
    return Side(config, board, "thief")


def test_each_side_starts_on_its_contracted_cell(config, board):
    assert _police(config, board).position == tuple(config.cop_start)
    assert _thief(config, board).position == tuple(config.thief_start)


def test_we_walk_our_own_piece(config, board):
    side = _thief(config, board)

    assert side.walk("MOVE:S") == (4, 3)


def test_a_move_off_the_board_resolves_to_stay(config, board):
    """The engine's own rule, applied to one piece instead of two."""
    side = _police(config, board)

    assert side.walk("MOVE:N") == tuple(config.cop_start)


def test_a_move_into_a_barrier_resolves_to_stay(config, board):
    board.place_barrier((4, 3))
    side = _thief(config, board)

    assert side.walk("MOVE:S") == tuple(config.thief_start)


def test_both_sides_emit_their_own_trail(config, board):
    """SPEC 5, confirmed with ali-ahm1: "each peer emits its own". A cop that
    sent `{}` would receive their positions while disclosing none of its own,
    and with the sides swapping every sub-game that is worth a series."""
    police, thief = _police(config, board), _thief(config, board)

    assert police.smell_grid() and thief.smell_grid()
    assert police.smell_grid() != thief.smell_grid()


def test_each_trail_is_centred_on_that_peers_own_start(config, board):
    police, thief = _police(config, board), _thief(config, board)
    cop_row, cop_col = config.cop_start
    thief_row, thief_col = config.thief_start

    assert max(police.smell_grid(), key=police.smell_grid().get) == \
        f"{cop_row},{cop_col}"
    assert max(thief.smell_grid(), key=thief.smell_grid().get) == \
        f"{thief_row},{thief_col}"


def test_the_trail_follows_our_piece(config, board):
    """The cell we now stand on is among the strongest, not uniquely so.

    Under the agreed subtractive decay the start cell and the cell we step
    onto tie exactly: (0,0) decays 0.9 -> 0.8 and takes +0.6 from the new
    kernel, while (1,0) decays 0.6 -> 0.5 and takes +0.9. Both 1.4. The
    geometric form broke that tie by a hundredth, which was luck. A far cell
    is what actually separates.
    """
    police = _police(config, board)
    police.walk("MOVE:S")
    grid = police.smell_grid()

    assert grid["1,0"] == max(grid.values())
    assert grid["2,0"] < grid["1,0"]
