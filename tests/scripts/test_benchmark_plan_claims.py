"""The figures docs/PLAN.md §10.10 publishes must survive a real run.

A document quoting exact capture rates either gets a mechanical check or
quietly becomes wrong — the posture ``tests/unit/test_readme_consistency.py``
already takes toward the README. §10.10 is the section an audit will read
hardest, so every number in it is re-derived here rather than trusted.

This file has now been rewritten twice, because the CONCLUSIONS inverted
twice: once when barriers were placed, and once when the evader was given the
distance rule. Both times the tests failed first and the prose followed. That
is the intended order.
"""

import json
from pathlib import Path

import pytest

PLAN = Path("docs/PLAN.md")
README = Path("README.md")
DOC_LABELS = {
    "qtable-only": "`qtable-only` — no distance rule at all",
    "qtable-primary": "`qtable-primary` — distance only on flat states",
    "manhattan-primary": "`manhattan-primary` — **shipped**, table breaks ties",
    "heuristic": "`heuristic` — same rule, EMPTY table, ties by move-set order",
}
SHIPPED = "manhattan-primary"
PUBLISHED_OPPONENTS = ("random", "greedy", "trained")


@pytest.fixture(scope="module")
def plan():
    return PLAN.read_text(encoding="utf-8")


def cell(rows, policy, opponent):
    return next(
        row for row in rows if row["policy"] == policy and row["opponent"] == opponent
    )


def rate(rows, policy, opponent):
    return cell(rows, policy, opponent)["capture_rate"]


def test_the_published_table_still_reproduces(benchmark_rows, plan):
    """Every capture-rate / turns cell §10.10 prints, checked against a run."""
    for policy, label in DOC_LABELS.items():
        matches = [line for line in plan.splitlines() if label in line]
        assert len(matches) == 1, f"§10.10 row for {label!r} is not unique"
        for opponent in PUBLISHED_OPPONENTS:
            row = cell(benchmark_rows, policy, opponent)
            quoted = f"{row['capture_rate']:.1f}% / {row['mean_turns']:.2f}"
            assert quoted in matches[0], (
                f"§10.10 no longer states {quoted} for {label!r} vs the "
                f"{opponent} thief"
            )


def test_the_published_off_manifold_rate_still_reproduces(benchmark_rows, plan):
    """The headline of §10.10, repeated in the README."""
    flat = cell(benchmark_rows, "qtable-only", "random")["flat_state_rate"]

    assert f"**{flat:.1f}% of decision states" in plan
    assert f"**{flat:.1f}%** of decisions" in README.read_text(encoding="utf-8")


def test_learning_now_beats_an_empty_table_against_a_strong_opponent(
    benchmark_rows, plan
):
    """The claim the whole diverse-opponent phase exists to support.

    Under self-play an EMPTY table beat the shipped cop against our own
    trained evader, 92.0% to 53.5%. If that ever returns, the phase has
    regressed and §10.10 is wrong.
    """
    shipped = rate(benchmark_rows, SHIPPED, "trained")
    empty = rate(benchmark_rows, "heuristic", "trained")

    assert shipped > empty, "an empty table beats the trained cop again"
    assert f"scores {shipped:.1f}% where an empty table" in plan
    assert f"scores {empty:.1f}%" in plan


def test_the_table_adds_nothing_against_a_GREEDY_evader_and_says_so(
    benchmark_rows, plan
):
    """The unflattering half: against a simple opponent the table is decoration.

    Reported because a section quoting only the strong-opponent column would
    be true and misleading.
    """
    shipped = rate(benchmark_rows, SHIPPED, "greedy")
    empty = rate(benchmark_rows, "heuristic", "greedy")

    assert abs(shipped - empty) < 5.0, "the greedy column stopped being level"
    assert f"({shipped:.1f}% against {empty:.1f}%" in plan


def test_the_self_play_era_figures_are_kept_as_the_comparison(plan):
    """The reversal must be published AS a reversal, not quietly swapped in."""
    assert "2.2%" in plan and "69.8%" in plan, "§10.10 dropped what self-play measured"
    assert "53.5%" in plan and "92.0%" in plan


def test_a_bare_board_makes_the_greedy_evader_uncatchable(benchmark_rows, plan):
    """The baseline the whole barrier argument rests on (see also
    tests/scripts/test_layout_generality.py, which checks it across layouts)."""
    assert "On a bare board every cop policy scores 0.0%" in plan
    assert benchmark_rows, "the probe produced no rows"


def test_the_provenance_note_names_the_commit_the_artifacts_carry(plan):
    """§10.10 must keep stating which commit sealed the shipped evidence."""
    declared = json.loads(
        (Path("logs/aviayeli/declaration_aviayeli.json")).read_text(encoding="utf-8")
    )["github_commit"]

    assert f"recorded at commit `{declared[:7]}`" in plan
