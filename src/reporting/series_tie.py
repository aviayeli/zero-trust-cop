"""The series tie award (PRD 21 Part 3, Appendix F Table 17, קבוע at 2).

Its own module because BOTH settlement scopes need it -- ``settlement.py``
builds our historical five-key scope and ``official_scope.py`` the league's
Appendix-F one -- and because adding it inline pushed ``settlement.py`` to 171
lines, over the project's 150 ceiling. PLAN 21 named that outcome in advance:
extract the shared helper rather than bend the ceiling.

``tie_score`` is always passed in, read from the agreed config by the caller.
Appendix F fixes it at 2, so there is exactly one correct value -- but the
constitution still forbids a literal at the call site, and a re-negotiated
table must move the award with it.
"""

from __future__ import annotations


def award_series_tie(total: dict, tie_score: int) -> dict:
    """Equal cumulative points -> ``tie_score`` to EACH side.

    "ניקוד לכל צד כאשר הניקוד המצטבר של כל המשחקונים מול יריבה מסתיים בתיקו"
    -- points to each side when the CUMULATIVE score of all sub-games against
    an opponent ends in a tie. The book places it at series level in three
    independent spots.

    THE TRIGGER IS CUMULATIVE POINTS, NOT A 3-3 SPLIT. Three wins as cop at
    20 each against three as thief at 10 each is 60-30: an even sub-game
    split with a decisive winner. Keying the award on sub-games won would
    award tie points to a series that has a winner, and would miss a real
    45-45 tie that happened to fall 4-2.

    Equal totals plus an equal award stay equal, so ``winner_group`` remains
    None and ``series_tie`` remains true either way -- the award changes the
    figures both teams file, not who won.
    """
    if not total or len(set(total.values())) != 1:
        return dict(total)
    return {group: points + tie_score for group, points in total.items()}


def winner_of(score: dict) -> str | None:
    """The higher-scoring group, or None on a tie.

    Shared by both settlement scopes so one definition governs both digests.
    A tie here is what makes a row's ``tie`` field derivable rather than worth
    signing, and after ``award_series_tie`` it is still a tie -- an equal
    award to equal totals leaves them equal.
    """
    ranked = sorted(score.items(), key=lambda pair: pair[1], reverse=True)
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]
