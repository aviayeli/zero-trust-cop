"""Claims, answers and survival on reference-v3 (PRD_10 FR4-FR5).

Split from `test_claims_side.py` at the 150-line limit; the seam is the
subject rather than the arithmetic. That module pins the PIECE — where it
starts, how it walks, what it discloses. This one pins what it CLAIMS, which
on this wire is the only thing that can end a sub-game.

The one-step lag is deliberate and tested: their claim for step n reaches us
after we have already sent step n, so we answer in step n+1. Answering "in
the same step if it happened to arrive first" is a race, and a race between
two peers on public tunnels is a coin flip neither side can debug.

The answer is HONEST because our own sealed chain carries `position` at every
step. A thief that answered "not caught" on a cell its own records place it
on has forged the evidence that convicts it, in front of the opponent's
re-hash at `submit_audit`.
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


def test_the_police_claims_the_cell_it_is_standing_on(config, board):
    side = _police(config, board)
    side.walk("MOVE:S")

    assert side.extras(step=1)["capture_claim"] == [1, 0]


def test_the_thief_claims_nothing(config, board):
    side = _thief(config, board)
    side.walk("MOVE:S")

    assert "capture_claim" not in side.extras(step=1)


def test_a_claim_on_our_cell_is_answered_caught_on_the_next_turn(config, board):
    thief = _thief(config, board)
    thief.walk("MOVE:STAY")

    thief.read({"step": 1, "capture_claim": list(config.thief_start)})

    assert thief.caught is True
    assert thief.extras(step=2)["claim_response"] == {
        "claim": list(config.thief_start), "caught": True,
    }


def test_a_claim_on_another_cell_is_answered_false_and_play_continues(config, board):
    thief = _thief(config, board)
    thief.walk("MOVE:STAY")

    thief.read({"step": 1, "capture_claim": [0, 0]})

    assert thief.caught is False
    assert thief.extras(step=2)["claim_response"] == {"claim": [0, 0], "caught": False}


def test_an_answer_is_sent_once_and_not_repeated(config, board):
    thief = _thief(config, board)
    thief.read({"step": 1, "capture_claim": [0, 0]})
    thief.extras(step=2)

    assert "claim_response" not in thief.extras(step=3)


def test_the_police_learns_of_the_capture_from_their_answer(config, board):
    police = _police(config, board)

    police.read({"step": 2, "claim_response": {"claim": [0, 0], "caught": True}})

    assert police.captured_them is True


def test_a_thief_answering_false_leaves_the_police_still_hunting(config, board):
    police = _police(config, board)

    police.read({"step": 2, "claim_response": {"claim": [0, 0], "caught": False}})

    assert police.captured_them is False


def test_the_thief_claims_survival_on_the_threshold_step(config, board):
    thief = _thief(config, board)

    assert "win_claim" not in thief.extras(step=config.survival_threshold - 1)
    assert thief.extras(step=config.survival_threshold)["win_claim"] == \
        {"type": "survival"}


def test_the_police_never_claims_survival(config, board):
    police = _police(config, board)

    assert "win_claim" not in police.extras(step=config.survival_threshold)


def test_their_win_claim_is_recorded(config, board):
    police = _police(config, board)

    police.read({"step": 35, "win_claim": {"type": "survival"}})

    assert police.they_claimed_survival is True
