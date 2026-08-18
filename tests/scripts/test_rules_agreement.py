"""Peers must agree on the RULES, not only on the board (audit, 6th sitting).

Split from `test_board_agreement.py` at the board/rules seam: that file
reached the 150-line limit, and these two disagreements fail differently from
a board mismatch and worse.

* `max_moves` produces identical play until the shorter limit fires, so it
  surfaces as a DivergenceError about termination after 35 SIGNED turns,
  blaming termination for a contract mismatch.
* `scoring` never diverges the engines at all. Both peers play the same match
  and report different outcomes, so no downstream check can catch it. It is
  caught here or not at all.
"""

import asyncio

import pytest

from engine.config import load_config
from scripts.board_agreement import BoardMismatchError, verify_board_agreement


@pytest.fixture
def config():
    return load_config("config/game.json")


def _rules(**overrides):
    """The contract fields a peer reports, with selective disagreement."""
    stated = {
        "max_moves": 35,
        "scoring": {
            "capture_cop": 20, "capture_thief": 5, "survival_cop": 5,
            "survival_thief": 10, "tie_score": 2, "technical_loss": 0,
        },
    }
    stated.update(overrides)
    return stated


def test_a_peer_on_a_different_move_limit_is_refused(config, peer_stub):
    """A max_moves mismatch does not diverge until turn 35 — far too late.

    Both engines agree on every position until the shorter limit fires, so
    the symptom is a DivergenceError about `is_terminated` after 35 signed
    turns, blaming termination for a contract disagreement.
    """
    peers = [
        peer_stub(14, **_rules()),
        peer_stub(14, "thief", **_rules(max_moves=50)),
    ]

    with pytest.raises(BoardMismatchError, match="max_moves"):
        asyncio.run(verify_board_agreement(peers, 14, config))


def test_a_peer_on_a_different_payoff_is_refused(config, peer_stub):
    """Scoring never diverges the ENGINE at all — it corrupts the RESULT.

    Two peers can play an identical match and report different outcomes, so
    this one produces no divergence to catch downstream. It has to be caught
    here or not at all.
    """
    peers = [
        peer_stub(14, **_rules()),
        peer_stub(14, "thief", **_rules(scoring=dict(_rules()["scoring"], capture_cop=99))),
    ]

    with pytest.raises(BoardMismatchError, match="capture_cop"):
        asyncio.run(verify_board_agreement(peers, 14, config))


def test_the_error_names_the_field_and_both_values(config, peer_stub):
    peers = [peer_stub(14, **_rules()), peer_stub(14, "thief", **_rules(max_moves=50))]

    with pytest.raises(BoardMismatchError) as raised:
        asyncio.run(verify_board_agreement(peers, 14, config))

    assert "50" in str(raised.value) and "35" in str(raised.value)


def test_agreeing_peers_pass_the_contract_check(config, peer_stub):
    peers = [peer_stub(14, **_rules()), peer_stub(14, "thief", **_rules())]

    asyncio.run(verify_board_agreement(peers, 14, config))


def test_a_peer_that_does_not_REPORT_the_rules_is_allowed(config, peer_stub):
    """Silence is not disagreement — the same rule the axis fields follow."""
    peers = [peer_stub(14), peer_stub(14, "thief")]

    asyncio.run(verify_board_agreement(peers, 14, config))


def test_the_check_is_skipped_when_no_config_is_supplied(peer_stub):
    """Existing callers that pass no config keep working unchanged."""
    peers = [peer_stub(14, **_rules(max_moves=999)), peer_stub(14, "thief", **_rules())]

    asyncio.run(verify_board_agreement(peers, 14))
