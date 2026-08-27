"""Settlement when the SIDES SWAP every sub-game (PRD_10 10.18).

`build_consensus` derived one role mapping from a single `our_role` and
applied it to every sub-game. That is right for a fixed-role match and wrong
for a reference-v3 series, where both teams agreed the sides alternate: under
one mapping, sub-games 2, 4 and 6 are scored with the roles inverted, and the
error lands in the SIGNED preimage of the artifact the grader verifies.

The format already carried the fix — `roles` lives INSIDE each sub-game row,
not beside them — so a row may declare the side we played that sub-game. A
row that declares nothing keeps the old behaviour exactly, which is what
keeps every hash the fixed-role path has ever settled reproducible.
"""

import json
from pathlib import Path

import pytest

from mcp_server import interop
from reporting.settlement import build_consensus

US = "aviayeli"
THEM = "groupb"


@pytest.fixture
def config():
    return json.loads(Path("config/game.json").read_text(encoding="utf-8"))


def _game(number, captured, our_role=None, reason=None):
    game = {"game_number": number, "captured": captured, "turns": 12,
            "terminal_reason": reason or ("capture" if captured else "survival")}
    if our_role is not None:
        game["our_role"] = our_role
    return game


def _consensus(config, games, our_role="cop"):
    return build_consensus({"game_id": interop.game_id(US, THEM), "games": games},
                           config, group_id=US, opponent_id=THEM, our_role=our_role)


def test_each_row_names_the_sides_that_sub_game_was_played_on(config):
    rows = _consensus(config, [_game(1, True, our_role="cop"),
                               _game(2, True, our_role="thief")])["sub_games"]

    assert rows[0]["roles"] == {"cop": US, "thief": THEM}
    assert rows[1]["roles"] == {"cop": THEM, "thief": US}


def test_the_same_outcome_scores_to_the_OTHER_group_when_we_swapped(config):
    """A capture is worth `capture_cop` to whoever was the cop THAT sub-game."""
    rows = _consensus(config, [_game(1, True, our_role="cop"),
                               _game(2, True, our_role="thief")])["sub_games"]

    assert rows[0]["score"][US] == config["scoring"]["capture_cop"]
    assert rows[1]["score"][US] == config["scoring"]["capture_thief"]


def test_the_aggregate_adds_up_across_swapped_sides(config):
    """Capture as cop then capture as thief is 20 + 5 on BOTH sides -- a level
    series, so Appendix F's tie award applies (PRD 21 Part 3).

    This test previously expected 25 and silently encoded the missing rule:
    two teams would have filed 25 and 27 for one match. The award is now part
    of the expectation rather than absent from it.
    """
    scoring = config["scoring"]
    consensus = _consensus(config, [_game(1, True, our_role="cop"),
                                    _game(2, True, our_role="thief")])
    earned = scoring["capture_cop"] + scoring["capture_thief"]
    awarded = earned + scoring["tie_score"]

    assert consensus["aggregate"]["total_score"][US] == awarded
    assert consensus["aggregate"]["total_score"][THEM] == awarded
    assert consensus["aggregate"]["series_tie"] is True
    assert consensus["aggregate"]["winner_group"] is None


def test_the_wire_spelling_police_is_accepted_in_a_row(config):
    """Our peers are named police/thief; the signed preimage says cop/thief.
    The alias has to apply per row too, or a row silently raises."""
    rows = _consensus(config, [_game(1, True, our_role="police")])["sub_games"]

    assert rows[0]["roles"] == {"cop": US, "thief": THEM}


def test_a_row_that_declares_nothing_keeps_the_series_role(config):
    """The fixed-role path must be untouched: every hash it has settled live
    reproduces only if an undeclared row behaves exactly as before."""
    rows = _consensus(config, [_game(1, True), _game(2, False)],
                      our_role="thief")["sub_games"]

    assert all(row["roles"] == {"thief": US, "cop": THEM} for row in rows)


def test_an_unknown_role_in_a_row_is_refused_not_defaulted(config):
    """A defaulted side scores the sub-game for the wrong group, silently."""
    with pytest.raises(ValueError, match="our_role"):
        _consensus(config, [_game(1, True, our_role="detective")])
