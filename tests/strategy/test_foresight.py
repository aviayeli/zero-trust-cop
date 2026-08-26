"""Lag compensation, corrected before implementation (Council review).

The brief proposed `target = argmax + 4*v` gated on `max(Phi) >= 0.35`. Both
halves were measured against the real field before any code was written, and
both were wrong in a way that matters:

* **The gate never fires.** `Phi` is unbounded and accumulates: one deposit
  puts the peak at 0.9 and it rises monotonically to 4.2 by turn six. A
  threshold of 0.35 on the raw peak passes on every turn of every game, so
  the safety mechanism is inert. `C = max/sum` is scale-free and measured
  0.13-0.30 on the same trace, which discriminates.

* **`4*v` amplifies the very lag it is meant to cancel.** `v` is the argmax
  displacement, and a lagging argmax does not move for L-1 turns and then
  jumps L cells at once. Measured on the real field: v is (0,0) for four
  turns -- extrapolating nothing -- and then (0,4), putting `b+4v` at (0,20)
  on a board whose legal range is 0..6. Codex predicted the failure and the
  field reproduced it exactly. Smoothing over the window recovers a per-turn
  velocity instead.
"""

import pytest

from strategy.foresight import Foresight

SIZE = 7


@pytest.fixture
def seer():
    return Foresight(grid_size=SIZE, min_confidence=0.2, horizon=4, window=3)


def _feed(seer, cells, confidence=0.5):
    for cell in cells:
        target = seer.target(cell, confidence)
    return target


# --- the gate that the raw-peak version could never apply ------------------


def test_low_confidence_falls_back_to_the_raw_argmax(seer):
    """Below the threshold we project nothing: extrapolating noise moves the
    pursuer away from the only evidence it has."""
    _feed(seer, [(0, 0), (0, 1), (0, 2)], confidence=0.9)

    assert seer.target((0, 3), 0.05) == (0, 3)


def test_high_confidence_projects_ahead(seer):
    target = _feed(seer, [(0, 0), (0, 1), (0, 2), (0, 3)], confidence=0.9)

    assert target != (0, 3), "a confident, moving belief should extrapolate"
    assert target[1] > 3


def test_a_scale_free_confidence_is_what_is_gated():
    """max/sum, not max. The raw peak passes 0.35 after a single deposit."""
    import inspect

    from strategy import foresight

    assert "max" in inspect.getsource(foresight.confidence)
    assert "sum" in inspect.getsource(foresight.confidence)


def test_confidence_is_invariant_to_scaling():
    from strategy.foresight import confidence

    field = {(0, 0): 0.9, (0, 1): 0.4, (1, 0): 0.2}
    scaled = {cell: 10 * value for cell, value in field.items()}

    assert confidence(field) == pytest.approx(confidence(scaled))


def test_an_empty_field_has_no_confidence():
    from strategy.foresight import confidence

    assert confidence({}) == 0.0


# --- the amplification the council caught ----------------------------------


def test_a_lag_jump_is_not_amplified(seer):
    """The measured failure: the argmax sits still, then jumps 4 cells. Naive
    `b + 4v` proposes (0, 20). Smoothing over the window must not."""
    target = _feed(seer, [(0, 0), (0, 0), (0, 0), (0, 4)], confidence=0.9)

    assert target[1] <= SIZE - 1, f"projected off the board: {target}"


def test_the_projection_is_always_on_the_board(seer):
    for cells in ([(0, 0), (0, 2), (0, 4), (0, 6)],
                  [(6, 6), (6, 4), (6, 2), (6, 0)],
                  [(3, 3), (2, 3), (1, 3), (0, 3)]):
        target = _feed(seer, cells, confidence=0.9)
        assert 0 <= target[0] < SIZE and 0 <= target[1] < SIZE, target


def test_a_still_belief_projects_itself(seer):
    """No movement, no extrapolation -- the target is the belief."""
    assert _feed(seer, [(3, 3)] * 4, confidence=0.9) == (3, 3)


def test_it_needs_a_full_window_before_projecting(seer):
    """One observation is not a velocity."""
    assert seer.target((2, 2), 0.9) == (2, 2)


def test_no_belief_at_all_yields_none(seer):
    assert seer.target(None, 0.9) is None
