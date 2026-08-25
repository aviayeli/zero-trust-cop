"""A cop standing on its own believed target has refuted that belief (PRD_18).

In three graded cop sub-games ours emitted MOVE:STAY for exactly 16
consecutive turns each -- 52% of all cop turns -- and never captured. Replaying
the sealed log against the opponent's own transmitted grids gives it exactly:
their argmax parked at (6,6) for ~18 turns, we chased it, we ARRIVED on it,
the believed cell became our own cell, `relative == (0,0)` made STAY uniquely
distance-optimal, and STAY kept us there.

The Q-table cannot rescue that: `manhattan_primary_action` lets it rank only
WITHIN the distance-optimal set, and that set is {STAY} alone.

On a wire with no position, "I am standing on the target and have no capture
to claim" is the strongest refutation available, and it needs no model of the
opponent's honesty.
"""

import pytest

from strategy.thaw import Thaw


@pytest.fixture
def cop():
    return Thaw(role="cop", max_consecutive_stay=3)


@pytest.fixture
def thief():
    return Thaw(role="thief", max_consecutive_stay=3)


# --- the falsified belief ---------------------------------------------------


def test_a_cop_on_its_own_believed_cell_may_not_stay(cop):
    """The whole defect, in one assertion."""
    assert "STAY" in cop.forbid(position=(6, 6), belief=(6, 6))


def test_a_cop_whose_belief_is_elsewhere_is_untouched(cop):
    """No behaviour change on the ordinary path."""
    assert cop.forbid(position=(6, 6), belief=(3, 3)) == frozenset()


def test_a_cop_with_no_belief_at_all_is_untouched(cop):
    assert cop.forbid(position=(0, 0), belief=None) == frozenset()


def test_a_thief_may_still_stand_on_its_believed_cell(thief):
    """FR4: standing still is legitimate evasion, and the thief is not the
    one being lured onto a fake target."""
    assert thief.forbid(position=(6, 6), belief=(6, 6)) == frozenset()


# --- the consecutive-STAY bound (FR2, both roles) ---------------------------


@pytest.mark.parametrize("role", ["cop", "thief"])
def test_a_run_of_stays_is_bounded(role):
    thaw = Thaw(role=role, max_consecutive_stay=3)
    for _ in range(3):
        assert "STAY" not in thaw.forbid(position=(1, 1), belief=(4, 4))
        thaw.took("STAY")

    assert "STAY" in thaw.forbid(position=(1, 1), belief=(4, 4))


def test_a_real_move_resets_the_run(thief):
    for _ in range(3):
        thief.took("STAY")
    thief.took("N")

    assert "STAY" not in thief.forbid(position=(1, 1), belief=(4, 4))


# --- preferring somewhere new (FR3) ----------------------------------------


def test_it_prefers_a_cell_it_has_not_stood_on(cop):
    """A random walk re-treads; a sweep does not."""
    cop.took("N", position=(5, 6))
    cop.took("N", position=(4, 6))

    assert cop.unvisited((5, 6)) is False
    assert cop.unvisited((3, 6)) is True


def test_the_bound_is_configured_not_inlined():
    """FR5. A literal here is the hardcoded tunable the constitution bans."""
    import inspect

    from strategy import thaw as module
    from strategy.settings import load_strategy_settings

    assert load_strategy_settings("police").max_consecutive_stay >= 1
    source = inspect.getsource(module)
    assert "max_consecutive_stay: int" in source or "max_consecutive_stay" in source
    assert " = 3" not in source and " = 5" not in source


# --- and the live loop must actually consult it ----------------------------


def test_the_match_chooser_applies_the_thaw():
    """The rule is worthless if the runner never asks it. `_chooser` is what
    the live series calls every step."""
    import inspect

    from scripts import claims_adapters

    source = inspect.getsource(claims_adapters._chooser)
    assert "thaw.forbid(" in source, "the live chooser ignores the thaw"
    assert "thaw.took(" in source, "the STAY run is never counted"


def test_the_thaw_is_built_per_sub_game():
    """Visited cells and the STAY run are per-sub-game; carrying either across
    a boundary would judge a new board by an old walk."""
    import inspect

    from scripts import claims_runner

    source = inspect.getsource(claims_runner.play_series)
    assert "Thaw(" in source
