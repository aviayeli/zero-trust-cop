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
PUBLISHED_OPPONENTS = ("random", "trained")


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
    """58.2% is the headline of §10.10 and is repeated in the README."""
    rate = cell(benchmark_rows, "qtable-only", "random")["flat_state_rate"]

    assert f"**{rate:.1f}% of decision states" in plan
    assert f"**{rate:.1f}%** of decisions" in README.read_text(encoding="utf-8")


def test_no_cop_catches_a_greedy_evader_on_a_bare_grid(benchmark_rows, plan):
    """§10.10 calls this structural, so it must stay measured, not asserted."""
    greedy = [row for row in benchmark_rows if row["opponent"] == "greedy"]

    assert greedy, "the greedy evader is part of the published opponent set"
    assert all(row["capture_rate"] == 0.0 for row in greedy)
    assert "all four score 0.0%" in plan


def test_each_step_of_the_progression_gains_ground(benchmark_rows):
    """§10.10 presents four policies as a progression; it must stay ordered."""
    for opponent in {row["opponent"] for row in benchmark_rows}:
        rates = [
            cell(benchmark_rows, policy, opponent)["capture_rate"]
            for policy in ("qtable-only", "qtable-primary", SHIPPED, "heuristic")
        ]

        assert rates == sorted(rates), f"the progression inverted vs {opponent}"


def test_the_learned_tie_break_still_costs_ground_against_the_heuristic(
    benchmark_rows, plan
):
    """The section's least flattering claim, and the one most likely to rot.

    `manhattan-primary` and `heuristic` run the SAME distance rule and differ
    only in how a tie is settled. If the learned values ever stop costing
    ground, §10.10's headline finding is wrong and must be rewritten.
    """
    shipped = cell(benchmark_rows, SHIPPED, "trained")["capture_rate"]
    heuristic = cell(benchmark_rows, "heuristic", "trained")["capture_rate"]

    assert shipped < heuristic, "the learned tie-break no longer costs ground"
    assert f"cost **{heuristic - shipped:.1f} points**" in plan
    assert "NET NEGATIVE as a tie-breaker" in plan


def test_the_published_swap_gain_is_computed_from_raw_rates(benchmark_rows, plan):
    """Subtracting the table's ROUNDED cells gives a different, wrong number."""
    before = cell(benchmark_rows, "qtable-primary", "trained")["capture_rate"]
    after = cell(benchmark_rows, SHIPPED, "trained")["capture_rate"]

    assert f"project**: +{after - before:.1f}" in plan


def test_the_shipped_policy_matches_the_heuristic_against_a_random_thief(
    benchmark_rows,
):
    """Parity is claimed for the random opponent only, and must hold."""
    shipped = cell(benchmark_rows, SHIPPED, "random")["capture_rate"]

    assert shipped == cell(benchmark_rows, "heuristic", "random")["capture_rate"]


def test_the_provenance_note_names_the_commit_the_artifacts_carry(plan):
    """§10.10 must keep stating which commit sealed the shipped evidence."""
    declared = json.loads(
        (Path("logs/aviayeli/declaration_aviayeli.json")).read_text(encoding="utf-8")
    )["github_commit"]

    assert f"recorded at commit `{declared[:7]}`" in plan
