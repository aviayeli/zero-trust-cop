"""The two capture families we never implemented (SPEC §3.1, PRD_10 10.23).

A capture settles three ways in this league and we encoded ONE:

1. co-location — the cop claims a cell and the thief is on it;
2. **rule 46** — a barrier is placed on the thief's own cell;
3. **rule 47** — the thief is boxed in: every ORTHOGONAL neighbour is a
   barrier or off the board.

Families 2 and 3 are facts only the THIEF can observe, so the SPEC requires
them to be SAID: the thief sends `claim_response {claim: [own cell],
caught: true}` — a *concession*, naming its own cell rather than echoing the
cop's claim. A thief that stays silent is not conforming.

The cost of silence is not a lost point, it is a zeroed pair. The thief
settles CAPTURE from knowledge the cop does not have; the cop learns nothing,
waits out its budget and settles TIMEOUT; two honest peers then describe one
sub-game two ways, which is the contradictory-report shape App. E rule 35
zeroes. The kit reproduced exactly that three times between two copies of its
own sparring peer (issue #37).

This is live against rstabcde, not theoretical: their cop places barriers as
core strategy — nine placements per game in their last counted series — and
we ignored `barrier_placed` entirely.
"""

import pytest

from engine.board import Board
from engine.config import load_config
from mcp_server.claims_side import Side

CONCEDE = "claim_response"


@pytest.fixture
def config():
    return load_config("config/game.json")


@pytest.fixture
def thief(config):
    return Side(config, Board(config), "thief")


def _turn(step=1, sender="police", **extra):
    return dict({"step": step, "sender": sender, "hint": "", "smell_grid": {},
                 "commit": "a" * 64, "timestamp": "2026-08-24T00:00:00Z"}, **extra)


# --- rule 46: a barrier on our own cell ------------------------------------


def test_a_barrier_on_our_cell_is_a_capture(thief, config):
    thief.read(_turn(barrier_placed=list(config.thief_start)))

    assert thief.caught is True


def test_the_concession_names_OUR_cell_not_the_cell_they_claimed(thief, config):
    """A `caught: true` echoing the cop's claim is an ANSWER; one naming any
    other cell is a CONCESSION. They settle the same and differ at audit."""
    thief.read(_turn(barrier_placed=list(config.thief_start)))

    assert thief.extras(step=2)[CONCEDE] == {
        "claim": list(config.thief_start), "caught": True,
    }


def test_a_barrier_somewhere_else_is_not_a_capture(thief):
    thief.read(_turn(barrier_placed=[0, 6]))

    assert thief.caught is False
    assert CONCEDE not in thief.extras(step=2)


# --- rule 47: boxed in -----------------------------------------------------


def _box_in(side, cell, config, leave_open=None):
    """Barrier every orthogonal neighbour of `cell` that is on the board."""
    row, col = cell
    for step, (dr, dc) in enumerate(((-1, 0), (1, 0), (0, -1), (0, 1)), start=1):
        neighbour = (row + dr, col + dc)
        if neighbour == leave_open:
            continue
        if 0 <= neighbour[0] < config.grid_size and 0 <= neighbour[1] < config.grid_size:
            side.read(_turn(step=step, barrier_placed=list(neighbour)))


def test_a_thief_with_no_legal_move_is_captured(thief, config):
    _box_in(thief, config.thief_start, config)

    assert thief.caught is True


def test_one_open_neighbour_is_not_a_capture(thief, config):
    row, col = config.thief_start
    _box_in(thief, config.thief_start, config, leave_open=(row - 1, col))

    assert thief.caught is False


def test_the_board_EDGE_counts_as_enclosure(config):
    """Rule 47 says "a barrier OR off the board" — a corner needs two."""
    side = Side(config, Board(config), "police")  # cop_start is [0, 0]
    side.read(_turn(barrier_placed=[1, 0]))
    side.read(_turn(step=2, barrier_placed=[0, 1]))

    assert side.caught is True


def test_STAY_does_not_rescue_a_boxed_in_thief(thief, config):
    """The rule is about MOVEMENT, not intent — being able to stand still is
    not a legal move out."""
    _box_in(thief, config.thief_start, config)

    assert thief.caught is True


# --- the barriers also block US -------------------------------------------


def test_a_barrier_they_placed_blocks_our_own_walk(thief, config):
    row, col = config.thief_start
    thief.read(_turn(barrier_placed=[row + 1, col]))

    assert thief.walk("MOVE:S") == (row, col), "the move resolves to STAY"


def test_a_malformed_barrier_cell_is_ignored_not_fatal(thief):
    """Their serialiser's output. A bad cell must not end a live match."""
    thief.read(_turn(barrier_placed="not-a-cell"))
    thief.read(_turn(step=2, barrier_placed=[99, 99]))

    assert thief.caught is False
