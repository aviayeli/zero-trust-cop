"""Mechanics of the off-manifold probe: sampling, bounds, shape, and the CLI.

What the run MEANS — the figures docs/PLAN.md §10.10 publishes — is asserted
separately in ``test_benchmark_plan_claims.py``. This module only proves the
instrument is sound: that starts stay on the board, that a seed reproduces a
sample, and that a run returns structured rows rather than printed prose.
"""

import pytest

from scripts.benchmark_offmanifold import (
    benchmark,
    format_rows,
    load_benchmark_settings,
    main,
)
from scripts.offmanifold_probe import build_table, evaluate, start_pairs

METRICS = {"policy", "opponent", "capture_rate", "mean_turns", "flat_state_rate"}
POLICIES = ("qtable-only", "qtable-primary", "manhattan-primary", "heuristic")


@pytest.fixture
def opponents():
    return load_benchmark_settings()["opponents"]


def test_the_settings_come_from_config_not_from_source():
    """A sample size inlined in Python would be a hardcoded hyperparameter."""
    settings = load_benchmark_settings()

    assert settings["start_pairs"] > 0
    assert isinstance(settings["seed"], int)
    assert settings["opponents"]


def test_every_start_pair_is_on_the_board_and_distinct(config):
    pairs = start_pairs(config, 200, seed=7)

    assert len(pairs) == 200
    for cop, thief in pairs:
        assert cop != thief, "coincident starts would capture before a move"
        for row, col in (cop, thief):
            assert 0 <= row < config.grid_size
            assert 0 <= col < config.grid_size


def test_start_pairs_are_reproducible_from_the_seed(config):
    assert start_pairs(config, 50, seed=7) == start_pairs(config, 50, seed=7)


def test_a_different_seed_draws_a_different_sample(config):
    assert start_pairs(config, 50, seed=7) != start_pairs(config, 50, seed=8)


def test_a_run_returns_one_structured_row_per_policy_and_opponent(
    benchmark_rows, opponents
):
    assert len(benchmark_rows) == len(POLICIES) * len(opponents)
    assert {row["policy"] for row in benchmark_rows} == set(POLICIES)
    assert {row["opponent"] for row in benchmark_rows} == set(opponents)
    assert all(set(row) == METRICS for row in benchmark_rows)


def test_rates_are_percentages_and_turns_respect_the_move_limit(
    benchmark_rows, config
):
    for row in benchmark_rows:
        assert 0.0 <= row["capture_rate"] <= 100.0
        assert 0.0 <= row["flat_state_rate"] <= 100.0
        assert row["mean_turns"] is None or 0 < row["mean_turns"] <= config.max_moves


def test_a_policy_that_never_captures_reports_no_mean_turns(
    config, police_settings, thief_settings
):
    """Averaging an empty sample to 0.0 would read as the fastest pursuit.

    A greedy pursuer against a greedy evader on a bare grid never captures,
    which makes it the one cell guaranteed to have no turns to average.
    """
    cop = build_table(config, police_settings, "cop")
    evader = build_table(config, thief_settings, "thief")
    cell = evaluate(config, cop, evader, start_pairs(config, 10, seed=3), seed=3)

    assert cell["capture_rate"] == 0.0
    assert cell["mean_turns"] is None


def test_a_table_less_cop_is_wholly_off_manifold(benchmark_rows):
    """The heuristic carries no table, so every state it meets is flat."""
    assert all(
        row["flat_state_rate"] == 100.0
        for row in benchmark_rows
        if row["policy"] == "heuristic"
    )


def test_a_smaller_sample_still_produces_the_full_table(opponents):
    rows = benchmark(count=10)

    assert len(rows) == len(POLICIES) * len(opponents)


def test_format_rows_renders_a_line_for_every_row(benchmark_rows):
    rendered = format_rows(benchmark_rows).splitlines()

    assert len(rendered) == len(benchmark_rows) + 2, "expected header and separator"
    for row in benchmark_rows:
        assert any(row["policy"] in line for line in rendered[2:])


def test_format_rows_emits_well_formed_markdown(benchmark_rows):
    """A doubled pipe renders as an extra empty column, silently."""
    header, separator, *body = format_rows(benchmark_rows).splitlines()
    width = header.count("|")

    assert separator.count("|") == width
    assert all(line.count("|") == width for line in body)
    assert "||" not in separator


def test_format_rows_prints_no_turns_for_a_policy_that_never_won(benchmark_rows):
    greedy = [row for row in benchmark_rows if row["opponent"] == "greedy"]

    assert greedy, "the greedy evader is part of the published opponent set"
    assert all("n/a" in line for line in format_rows(greedy).splitlines()[2:])


def test_the_cli_prints_the_table_and_returns_the_rows(capsys, opponents):
    returned = main(["--start-pairs", "20"])

    assert len(returned) == len(POLICIES) * len(opponents)
    assert "capture_rate" in capsys.readouterr().out
