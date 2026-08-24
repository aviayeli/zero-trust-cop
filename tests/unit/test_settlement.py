"""The settlement consensus SCOPE -- what the signature is computed over.

The serialization half lives in ``test_settlement_signature.py``; these two
fail independently, and only that one is about bytes.

* SCOPE -- what the signature is computed OVER. A whole-report-minus-signature
  preimage is per-side BY CONSTRUCTION: our timestamps and token counts sit
  inside it, so two honest teams can never produce equal hashes. The
  interoperable scope is the trimmed ``symmetric_outcome`` -- everything two
  honest teams must agree on and nothing they may legitimately differ on. The
  sub-game rows carry FIVE keys; ``tie`` is derivable from
  ``winner_group is None`` and stays out of the preimage.
"""

import json
from pathlib import Path

import pytest

from mcp_server import interop
from reporting.settlement import CONSENSUS_ROW_KEYS, build_consensus, sign_consensus

US = "aviayeli"
THEM = "groupb"


@pytest.fixture
def config():
    return json.loads(Path("config/game.json").read_text(encoding="utf-8"))


def _result(games):
    return {"game_id": interop.game_id(US, THEM), "games": games}


def _game(number, captured, reason="capture"):
    return {"game_number": number, "captured": captured,
            "terminal_reason": reason, "turns": 12}


@pytest.fixture
def consensus(config):
    return build_consensus(_result([_game(1, True), _game(2, False, "max_moves_reached")]),
                           config, group_id=US, opponent_id=THEM, our_role="cop")


def test_the_scope_is_the_three_agreed_sections(consensus):
    assert sorted(consensus) == ["aggregate", "game_id", "sub_games"]


def test_each_sub_game_row_carries_exactly_five_keys(consensus):
    """`tie` is derivable from winner_group and stays OUT of the preimage:
    every hash ever settled live reproduces only under the five-key row."""
    assert CONSENSUS_ROW_KEYS == (
        "result", "roles", "score", "sub_game_number", "winner_group"
    )
    for row in consensus["sub_games"]:
        assert sorted(row) == sorted(CONSENSUS_ROW_KEYS)


def test_the_aggregate_carries_exactly_the_agreed_keys(consensus):
    assert sorted(consensus["aggregate"]) == [
        "series_tie", "sub_games_won", "ties", "total_score", "winner_group"
    ]


def test_scores_come_from_the_agreed_contract_not_from_source(config):
    """Project constitution: no scoring constant inlined. A capture pays the
    cop `capture_cop` and the thief `capture_thief`, both read from config."""
    scoring = config["scoring"]
    consensus = build_consensus(_result([_game(1, True)]), config,
                                group_id=US, opponent_id=THEM, our_role="cop")

    assert consensus["sub_games"][0]["score"][US] == scoring["capture_cop"]
    assert consensus["sub_games"][0]["score"][THEM] == scoring["capture_thief"]


def test_a_survival_pays_the_thief(config):
    consensus = build_consensus(
        _result([_game(1, False, "max_moves_reached")]), config,
        group_id=US, opponent_id=THEM, our_role="cop")
    row = consensus["sub_games"][0]

    assert row["score"][THEM] == config["scoring"]["survival_thief"]
    assert row["winner_group"] == THEM


def test_the_roles_name_which_group_played_which_side(consensus):
    assert consensus["sub_games"][0]["roles"] == {"cop": US, "thief": THEM}


def test_both_peers_derive_the_same_consensus_from_their_own_side(config):
    """The whole point: the preimage is a pure function of shared facts, so
    the opponent computes it from THEIR side and reaches the same bytes."""
    games = [_game(1, True), _game(2, False, "max_moves_reached")]
    ours = build_consensus(_result(games), config, group_id=US,
                           opponent_id=THEM, our_role="cop")
    theirs = build_consensus(_result(games), config, group_id=THEM,
                             opponent_id=US, our_role="thief")

    assert ours == theirs
    assert interop.report_consensus_signature(ours) == \
        interop.report_consensus_signature(theirs)


def test_the_aggregate_totals_the_sub_games(consensus, config):
    scoring = config["scoring"]
    aggregate = consensus["aggregate"]

    assert aggregate["total_score"][US] == scoring["capture_cop"] + scoring["survival_cop"]
    assert aggregate["total_score"][THEM] == scoring["capture_thief"] + scoring["survival_thief"]
    assert aggregate["sub_games_won"] == {US: 1, THEM: 1}


def test_an_equal_series_is_a_tie_with_no_winner(config):
    """`series_tie` is signed; `tie` per row is not, being derivable."""
    consensus = build_consensus(
        _result([_game(1, True), _game(2, True)]), config,
        group_id=US, opponent_id=THEM, our_role="cop")
    # cop wins both; make it symmetric by scoring the mirror series too.
    mirrored = build_consensus(
        _result([_game(1, True), _game(2, True)]), config,
        group_id=US, opponent_id=THEM, our_role="thief")

    assert consensus["aggregate"]["winner_group"] == US
    assert consensus["aggregate"]["series_tie"] is False
    assert mirrored["aggregate"]["winner_group"] == THEM
