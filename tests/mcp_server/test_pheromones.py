"""Behavioural tests for the police pheromone belief field."""

from dataclasses import replace

import pytest

from engine.config import load_config
from strategy.pheromones import PheromoneField


def _config(**changes):
    return replace(load_config("config/game.json"), **changes)


def test_recurrence_decays_a_seeded_cell_each_tick():
    field = PheromoneField(_config())
    field.deposit((3, 3))

    field.advance()
    assert field.intensity((3, 3)) == pytest.approx(0.810000)
    field.advance()
    assert field.intensity((3, 3)) == pytest.approx(0.729000)
    field.advance()
    assert field.intensity((3, 3)) == pytest.approx(0.656100)


def test_negative_delta_is_clamped_to_zero():
    field = PheromoneField(_config())
    field.deposit((3, 3))

    field.advance([((3, 3), -10.0)])

    assert field.intensity((3, 3)) == 0.0


def test_kernel_has_exact_linear_values_by_manhattan_distance():
    field = PheromoneField(_config())
    centre = (3, 3)
    field.deposit(centre)

    assert field.intensity(centre) == 0.9
    assert field.intensity((2, 3)) == 0.6
    assert field.intensity((1, 3)) == 0.3
    for row in range(1, 6):
        for col in range(1, 6):
            if 3 <= abs(row - centre[0]) + abs(col - centre[1]) <= 4:
                assert field.intensity((row, col)) == 0.0


def test_kernel_has_thirteen_nonzero_cells():
    field = PheromoneField(_config())
    field.deposit((3, 3))

    assert len(field.heatmap()) == 13


def test_edge_kernel_is_clipped_to_the_board():
    config = _config()
    field = PheromoneField(config)
    field.deposit((0, 0))

    assert all(
        0 <= row < config.grid_size and 0 <= col < config.grid_size
        for row, col in field.heatmap()
    )
    assert len(field.heatmap()) < 13


def test_edge_kernel_never_wraps_to_opposite_corner():
    config = _config()
    field = PheromoneField(config)
    field.deposit((0, 0))

    assert field.intensity((config.grid_size - 1, config.grid_size - 1)) == 0.0


def test_overlapping_kernels_fuse_by_summation():
    field = PheromoneField(_config())
    field.deposit((3, 3))
    field.deposit((3, 4))

    assert field.intensity((3, 3)) == 1.5


def test_decay_is_global_across_separate_regions():
    field = PheromoneField(_config())
    field.deposit((1, 1))
    field.deposit((5, 5))

    field.advance()

    assert field.intensity((1, 1)) == pytest.approx(0.81)
    assert field.intensity((5, 5)) == pytest.approx(0.81)


def test_decay_factor_is_read_from_config():
    field = PheromoneField(_config(pheromone_decay=0.5))
    field.deposit((3, 3))

    field.advance()

    assert field.intensity((3, 3)) == pytest.approx(0.45)


def test_same_deposit_and_tick_sequence_is_deterministic():
    config = _config()
    first = PheromoneField(config)
    second = PheromoneField(config)
    sequence = (((2, 2),), (), ((4, 4),), ((3, 3),))

    for deposits in sequence:
        first.advance(deposits)
        second.advance(deposits)

    assert first.heatmap() == second.heatmap()


def test_strongest_cell_and_empty_field_behaviour():
    field = PheromoneField(_config())
    assert field.strongest() is None

    field.deposit((2, 2))
    field.advance()
    field.deposit((4, 4))

    assert field.strongest() == (4, 4)


@pytest.mark.parametrize("cell", [(-1, 0), (0, -1), (7, 0), (0, 7)])
def test_out_of_bounds_reads_and_deposits_fail_loudly(cell):
    field = PheromoneField(_config())

    with pytest.raises(ValueError):
        field.intensity(cell)
    with pytest.raises(ValueError):
        field.deposit(cell)
