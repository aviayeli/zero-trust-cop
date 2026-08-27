"""The series tie award (Appendix F Table 17, קבוע at 2).

"ניקוד לכל צד כאשר הניקוד המצטבר של כל המשחקונים מול יריבה מסתיים בתיקו"
-- points to each side when the CUMULATIVE score of all sub-games against an
opponent ends in a tie. Series level, in three independent placements.

We loaded tie_score from config and used it in the learning reward table, and
never applied it to a series total. A level series would have had us filing
45-45 while the opponent filed 47-47: two groups, one match, different
numbers on a scored field.

THE TRIGGER IS CUMULATIVE POINTS, NOT A 3-3 SPLIT. Three wins as cop at 20
each against three as thief at 10 each is 60-30 -- an even sub-game split with
a decisive winner. The second test below is the one that fails if anyone keys
the award on sub-games won.
"""

import json
from pathlib import Path

from reporting import official_scope
from reporting.series_tie import award_series_tie

EVIDENCE = Path("logs/evidence/ZeroOne0-vs-aviayeli")
HISTORICAL = "c39d331ce8c45e30823baf2aeae58053020836542aa6e14d584fa2a58af23ee6"
OFFICIAL = "5077306a3703467941ce7593bcf805a022c9f162588acc4f3feca97a045b0373"
THEIR_COMMIT = "62404917a4c43acdc600c4b72adecbbe8d6df341"


def test_a_level_series_awards_tie_score_to_both():
    awarded = award_series_tie({"aviayeli": 45, "them": 45}, 2)

    assert awarded == {"aviayeli": 47, "them": 47}


def test_a_three_three_split_with_unequal_points_gets_no_award():
    """Three wins as cop (20 each) against three as thief (10 each) is 60-30.
    An even sub-game split, a decisive series. Keying the award on 3-3 fails
    exactly here."""
    totals = {"aviayeli": 60, "them": 30}

    assert award_series_tie(dict(totals), 2) == totals


def test_a_four_two_split_with_equal_points_does_get_the_award():
    """The mirror: an uneven sub-game split can still be a points tie."""
    awarded = award_series_tie({"aviayeli": 45, "them": 45}, 2)

    assert awarded["aviayeli"] == 47 and awarded["them"] == 47


def test_tie_score_comes_from_the_agreed_config():
    """Read, never inlined -- Appendix F fixes it at 2, but the constitution
    still forbids a literal at the call site."""
    assert award_series_tie({"a": 10, "b": 10}, 5) == {"a": 15, "b": 15}


def test_a_level_series_stays_a_tie_after_the_award():
    """Equal totals plus an equal award are still equal: winner_group must
    stay null and series_tie true."""
    awarded = award_series_tie({"a": 45, "b": 45}, 2)

    assert len(set(awarded.values())) == 1


def test_the_two_settled_digests_still_reproduce():
    """Regression guard, not a migration: neither completed series was level,
    so no awarded row exists in either and both digests must be untouched."""
    result = json.loads((EVIDENCE / "result_ZeroOne0-vs-aviayeli.json").read_text())
    config = json.loads(
        (EVIDENCE / "config_ZeroOne0-vs-aviayeli_series.json").read_text())
    logs = {n: json.loads(
        (EVIDENCE / f"log_ZeroOne0-vs-aviayeli_g0{n}.json").read_text())
        for n in range(1, 7)}

    scope = official_scope.build(result, config, logs, THEIR_COMMIT)

    assert official_scope.digest(scope) == (OFFICIAL, 3997)
    assert result["mutual_agreement"]["sha256"] == HISTORICAL
