"""The figures docs/PLAN.md §10.10 publishes must survive a real run.

A document quoting exact capture rates either gets a mechanical check or
quietly becomes wrong — the posture ``tests/unit/test_readme_consistency.py``
already takes toward the README. §10.10 is the section an audit will read
hardest, so every number in it is re-derived here from
``scripts.benchmark_offmanifold`` rather than trusted.

Retraining the tables is therefore expected to fail these tests. That is the
point: the numbers move together with the policy or not at all.
"""

from pathlib import Path

import pytest

PLAN = Path("docs/PLAN.md")
README = Path("README.md")
# How §10.10's published table labels each policy the probe reports.
DOC_LABELS = {
    "trained": "Trained Q-table, no fallback (pre-fix)",
    "heuristic": "Greedy Manhattan heuristic alone",
    "trained+fallback": "Trained Q-table + distance fallback",
}
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
    rate = cell(benchmark_rows, "trained", "random")["flat_state_rate"]

    assert f"**{rate:.1f}% of decision states" in plan
    assert f"**{rate:.1f}%** of decisions" in README.read_text(encoding="utf-8")


def test_no_cop_catches_a_greedy_evader_on_a_bare_grid(benchmark_rows, plan):
    """§10.10 calls this structural, so it must stay measured, not asserted."""
    greedy = [row for row in benchmark_rows if row["opponent"] == "greedy"]

    assert greedy, "the greedy evader is part of the published opponent set"
    assert all(row["capture_rate"] == 0.0 for row in greedy)
    assert "all three score 0.0%" in plan


def test_the_fallback_never_costs_capture_rate(benchmark_rows):
    """§10.10 claims a gain on every opponent; a regression must fail here."""
    for opponent in {row["opponent"] for row in benchmark_rows}:
        before = cell(benchmark_rows, "trained", opponent)["capture_rate"]
        after = cell(benchmark_rows, "trained+fallback", opponent)["capture_rate"]

        assert after >= before, f"the fallback lost ground against {opponent}"


def test_the_plan_does_not_claim_heuristic_parity(benchmark_rows, plan):
    """The measured gap is the honest finding; §10.10 must keep stating it."""
    for opponent in PUBLISHED_OPPONENTS:
        assert (
            cell(benchmark_rows, "trained+fallback", opponent)["capture_rate"]
            < cell(benchmark_rows, "heuristic", opponent)["capture_rate"]
        ), f"the fallback now MATCHES the heuristic vs {opponent}; §10.10 is stale"
    assert "does **not** reach the pure" in plan
