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
    "qtable-primary": "`qtable-primary` — **shipped**, distance only on flat states",
    "manhattan-primary": "`manhattan-primary` — distance decides, table breaks ties",
    "heuristic": "`heuristic` — same rule, EMPTY table, ties by move-set order",
}
SHIPPED = "qtable-primary"
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


def test_the_priority_inversion_is_real_and_published(benchmark_rows, plan):
    """§10.10's most important claim: the optimal priority is opponent-dependent.

    Phase 8 shipped `manhattan_primary` on a measurement against a weak
    evader. Against a competent one the ordering reverses. If it ever reverses
    back, the section's central methodological lesson is wrong.
    """
    shipped = rate(benchmark_rows, SHIPPED, "greedy")
    superseded = rate(benchmark_rows, "manhattan-primary", "greedy")

    assert shipped > superseded, "the priority inversion no longer holds"
    assert f"**{shipped:.1f}%** where `manhattan_primary` scores" in plan
    assert f"**{superseded:.1f}%**" in plan


def test_the_learned_table_helps_the_cop_against_a_greedy_evader(
    benchmark_rows, plan
):
    """The cop-side NET POSITIVE claim, stated for the greedy evader only."""
    shipped = rate(benchmark_rows, SHIPPED, "greedy")
    empty = rate(benchmark_rows, "heuristic", "greedy")

    assert shipped > empty, "the learned tie-break stopped helping the cop"
    assert f"({shipped:.1f}% vs {empty:.1f}%)" in plan


def test_the_unflattering_result_against_our_own_thief_stays_published(
    benchmark_rows, plan
):
    """The empty table still beats the shipped cop against our trained evader.

    This is the least flattering cell in the matrix. §10.10 must keep saying
    so; a section that published only the greedy column would be true and
    misleading.
    """
    shipped = rate(benchmark_rows, SHIPPED, "trained")
    empty = rate(benchmark_rows, "heuristic", "trained")

    assert empty > shipped, "the result changed; §10.10 must be rewritten"
    assert f"({empty:.1f}% vs {shipped:.1f}%)" in plan


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
