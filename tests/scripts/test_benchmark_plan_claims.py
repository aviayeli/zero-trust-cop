"""The figures docs/PLAN.md §10.10 publishes must survive a real run.

A document quoting exact capture rates either gets a mechanical check or
quietly becomes wrong — the posture ``tests/unit/test_readme_consistency.py``
already takes toward the README. §10.10 is the section an audit will read
hardest, so every number in it is re-derived here from
``scripts.benchmark_offmanifold`` rather than trusted.

Retraining the tables is therefore expected to fail these tests. That is the
point: the numbers move together with the policy or not at all.
"""

import json
from pathlib import Path

import pytest

PLAN = Path("docs/PLAN.md")
README = Path("README.md")
# How §10.10's published table labels each policy the probe reports.
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
    """The off-manifold rate is §10.10's headline and is repeated in the README."""
    rate = cell(benchmark_rows, "qtable-only", "random")["flat_state_rate"]

    assert f"**{rate:.1f}% of decision states" in plan
    assert f"**{rate:.1f}%** of decisions" in README.read_text(encoding="utf-8")


def test_the_greedy_evader_is_catchable_now_that_barriers_are_placed(
    benchmark_rows, plan
):
    """The 0.0% result was structural to a BARE grid, and Phase 9 removed it.

    Barriers give a lone pursuer somewhere to corner against. If this ever
    returns to zero, §4.3 stopped populating the board and §10.10's headline
    claim is wrong.
    """
    greedy = [row for row in benchmark_rows if row["opponent"] == "greedy"]

    assert greedy, "the greedy evader is part of the published opponent set"
    shipped = cell(benchmark_rows, SHIPPED, "greedy")["capture_rate"]
    assert shipped > 0.0, "the greedy evader is uncatchable again"
    assert f"0.0% -> {shipped:.1f}%" in plan


def test_each_priority_step_gains_ground(benchmark_rows):
    """The three TABLE-bearing policies are a progression and must stay ordered.

    ``heuristic`` is deliberately excluded: it carries no learned values, so
    it is a baseline rather than a step, and on the barriered board it no
    longer tops the table (§10.10).
    """
    for opponent in {row["opponent"] for row in benchmark_rows}:
        rates = [
            cell(benchmark_rows, policy, opponent)["capture_rate"]
            for policy in ("qtable-only", "qtable-primary", SHIPPED)
        ]

        assert rates == sorted(rates), f"the progression inverted vs {opponent}"


def test_the_learned_tie_break_now_gains_ground_over_the_heuristic(
    benchmark_rows, plan
):
    """§10.10's headline REVERSED at Phase 9, so it must stay measured.

    `manhattan-primary` and `heuristic` run the SAME distance rule and differ
    only in how a tie is settled. On the bare grid the learned values cost
    13.5 points; on the barriered board they gain. If that inverts again the
    section is wrong and must be rewritten a second time.
    """
    for opponent in ("trained", "greedy"):
        shipped = cell(benchmark_rows, SHIPPED, opponent)["capture_rate"]
        heuristic = cell(benchmark_rows, "heuristic", opponent)["capture_rate"]

        assert shipped > heuristic, f"the learned tie-break lost ground vs {opponent}"
        assert f"**{shipped - heuristic:.1f} points**" in plan
    assert "NET POSITIVE as a tie-breaker" in plan


def test_the_published_swap_gain_is_computed_from_raw_rates(benchmark_rows, plan):
    """Subtracting the table's ROUNDED cells gives a different, wrong number."""
    before = cell(benchmark_rows, "qtable-primary", "trained")["capture_rate"]
    after = cell(benchmark_rows, SHIPPED, "trained")["capture_rate"]

    assert f"project**:\n      +{after - before:.1f} points" in plan


def test_the_shipped_policy_is_never_beaten_by_the_empty_table_baseline(
    benchmark_rows,
):
    """The baseline outscored the shipped policy before Phase 9; it must not now."""
    for opponent in ("random", "greedy", "trained"):
        shipped = cell(benchmark_rows, SHIPPED, opponent)["capture_rate"]
        baseline = cell(benchmark_rows, "heuristic", opponent)["capture_rate"]

        assert shipped >= baseline, f"the empty-table baseline wins vs {opponent}"


def test_the_provenance_note_names_the_commit_the_artifacts_carry(plan):
    """§10.10 must keep stating which commit sealed the shipped evidence."""
    declared = json.loads(
        (Path("logs/aviayeli/declaration_aviayeli.json")).read_text(encoding="utf-8")
    )["github_commit"]

    assert f"recorded at commit `{declared[:7]}`" in plan
