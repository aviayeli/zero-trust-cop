"""Appendix F's mandated values, checked against every config we ship.

The gap this closes: `min_games_to_pass` read 1 for ten days and through two
graded series. Table 18 marks it קבוע, and printed p.139 defines that status
as "ערך מחייב שאינו ניתן לשינוי כלל. סטייה מן הערך הזה פוסלת את הקבוצה" --
deviation disqualifies the group. Nothing here checked it, while a 150-line
ceiling and a documented test count were both mechanically enforced.

PROVENANCE: police_thief_p2p.pdf Appendix F is NOT in this repository. The
table is transcribed by SMNGRP05, who have the PDF, with printed page numbers
(status column p.135/p.139, values Tables 13/15/16/17/18). Adopted on their
transcription, not on our reading of the source.
"""

import json
from pathlib import Path

import pytest

from engine import appendix_f

CONFIGS = sorted(Path("config").glob("**/game.json"))


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_repo_ships_configs_to_check():
    assert CONFIGS, "no config/**/game.json found; this guard would be vacuous"


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: str(p))
def test_every_shipped_config_obeys_appendix_f(path):
    """Every config, not the one that happens to be loaded: our deviation
    existed in three files at once."""
    assert appendix_f.check(_load(path)) == []


def test_a_lowered_permanent_value_is_named_in_the_failure():
    """The exact bug that survived ten days. 'config invalid' would not have
    helped anyone find it."""
    config = _load(CONFIGS[0])
    config["network_and_league"]["min_games_to_pass"] = 1

    problems = appendix_f.check(config)

    assert len(problems) == 1
    message = problems[0]
    assert "min_games_to_pass" in message
    assert "1" in message and "2" in message
    assert "קבוע" in message


def test_zero_below_a_floor_fails():
    """SMNGRP05 lost 240 matches' work to max_barriers = 0 -- it reads as a
    clean symmetric experiment and is forbidden."""
    config = _load(CONFIGS[0])
    config["movement_and_barriers"]["max_barriers"] = 0

    problems = appendix_f.check(config)

    assert any("max_barriers" in p for p in problems)
    assert any("מינימום" in p for p in problems)


def test_raising_a_minimum_is_permitted():
    """מינימום may be raised by agreement -- only lowering is forbidden."""
    config = _load(CONFIGS[0])
    config["movement_and_barriers"]["max_barriers"] = 20

    assert appendix_f.check(config) == []


def test_changing_a_permanent_value_upward_still_fails():
    """קבוע is exact equality, not a floor."""
    config = _load(CONFIGS[0])
    config["scoring"]["tie_score"] = 3

    assert any("tie_score" in p for p in appendix_f.check(config))


def test_the_unmandated_pheromone_field_is_not_checked():
    """pheromone_min_center_intensity is absent from Table 16 (three rows).
    Negotiated, not mandated."""
    config = _load(CONFIGS[0])
    config["pheromones"]["pheromone_min_center_intensity"] = 0.42

    assert appendix_f.check(config) == []


def test_all_thirteen_permanent_and_nine_floor_fields_are_declared():
    assert len(appendix_f.FIXED) == 13
    assert len(appendix_f.FLOORS) == 9
