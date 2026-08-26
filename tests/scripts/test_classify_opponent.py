"""Classify an opponent from the only channel we actually have (Council).

The spec asked for a four-way classifier reading logs "as they are updated
during a live match". Two facts from the codebase reshape it:

* **Logs appear only when a sub-game CLOSES.** `claims_runner` calls
  `on_sub_game` after the audit, 35 turns in. There is no partially-written
  log to tail, so a file-watching classifier would classify nothing until the
  game it was meant to inform is over.

* **B and C are not separable from the scent alone.** We never observe a
  position; we observe a self-reported grid. A bluffer pins its argmax to a
  corner *precisely so it looks like* an honest corner-hider. Gemini put it
  plainly: within the window, C's real trail is masked by its own fake peak.

So the honest output is three classes, not four, plus a distinct upgrade path:
`CORNER_PARKED` becomes `BLUFFER` only when the pursuer stands on the parked
cell and has no capture to claim -- the same empirical refutation the thaw
uses. A classifier that claimed four from the grid would be inventing one.
"""


from scripts.classify_opponent import BLUFFER, CORNER_PARKED, RANDOM, STATIC, classify

SIZE = 7


def _grids(cells):
    """One transmitted grid per turn, peaked at each cell."""
    return [{f"{r},{c}": 0.9} for r, c in cells]


def test_a_parked_argmax_reads_as_corner_parked():
    assert classify(_grids([(6, 6)] * 5), SIZE) == CORNER_PARKED


def test_a_wandering_argmax_reads_as_random():
    assert classify(_grids([(3, 3), (3, 4), (2, 4), (2, 5), (1, 5)]), SIZE) == RANDOM


def test_an_argmax_that_never_moves_off_a_non_corner_reads_as_static():
    assert classify(_grids([(3, 3)] * 5), SIZE) == STATIC


def test_every_corner_counts_not_just_one():
    for corner in ((0, 0), (0, 6), (6, 0), (6, 6)):
        assert classify(_grids([corner] * 5), SIZE) == CORNER_PARKED, corner


def test_too_few_turns_yields_no_verdict():
    """A classifier that guesses from two turns is a coin flip with a label."""
    assert classify(_grids([(6, 6), (6, 6)]), SIZE) is None


def test_an_unreadable_grid_is_skipped_not_fatal():
    """Their serialiser, not ours. A malformed cell is a reason to learn
    nothing from that turn, never to crash mid-match."""
    grids = _grids([(6, 6)] * 4) + [{"not-a-cell": 1.0}]

    assert classify(grids, SIZE) in (CORNER_PARKED, None)


def test_bluffer_is_only_reachable_by_refutation():
    """The upgrade the grid alone can never justify."""
    from scripts.classify_opponent import refute

    assert refute(CORNER_PARKED, standing_on_belief=True, captured=False) == BLUFFER
    assert refute(CORNER_PARKED, standing_on_belief=True, captured=True) == CORNER_PARKED
    assert refute(CORNER_PARKED, standing_on_belief=False, captured=False) == CORNER_PARKED


def test_refutation_does_not_relabel_the_other_classes():
    for verdict in (RANDOM, STATIC):
        assert refute_stable(verdict) == verdict


def refute_stable(verdict):
    from scripts.classify_opponent import refute

    return refute(verdict, standing_on_belief=True, captured=False)


def test_the_warning_names_the_class_and_carries_colour():
    from scripts.classify_opponent import warning

    text = warning(BLUFFER)
    assert "BLUFFER" in text.upper()
    assert "\033[" in text, "the brief asked for an ANSI-coloured warning"


def test_no_verdict_produces_no_warning():
    from scripts.classify_opponent import warning

    assert warning(None) == ""
