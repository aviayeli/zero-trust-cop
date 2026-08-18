"""The deterministic barrier layout (PLAN.md §4.3).

``max_barriers`` was configured from Phase 0 and populated never, which is
what PLAN.md §10.10 measures as a 0.0% capture rate against a greedy evader:
a bare grid gives a lone pursuer nothing to corner against.

The layout is DERIVED from shared configuration rather than exchanged, so
both mirrored engines build the identical board without a wire message and
without trusting each other for it.
"""

from dataclasses import replace

import pytest

from engine.barriers import barrier_layout
from engine.config import load_config


@pytest.fixture
def config():
    """The shared contract, with barriers switched on at a known seed."""
    return replace(load_config("config/game.json"), barrier_seed=20260818)


def _free_space_is_connected(config, layout) -> bool:
    """Flood-fill the non-barrier cells from cop_start, independently of src."""
    size = config.grid_size
    start = tuple(config.cop_start)
    seen, frontier = {start}, [start]
    while frontier:
        row, col = frontier.pop()
        for delta_row, delta_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            cell = (row + delta_row, col + delta_col)
            if not (0 <= cell[0] < size and 0 <= cell[1] < size):
                continue
            if cell in layout or cell in seen:
                continue
            seen.add(cell)
            frontier.append(cell)
    reachable = size * size - len(layout)
    return len(seen) == reachable


def test_the_layout_places_exactly_max_barriers(config):
    assert len(barrier_layout(config)) == config.max_barriers


def test_the_layout_is_identical_for_the_same_seed(config):
    """Both peers derive the board from config alone; drift is a divergence."""
    assert barrier_layout(config) == barrier_layout(config)


def test_a_different_seed_moves_the_barriers(config):
    other = replace(config, barrier_seed=config.barrier_seed + 1)

    assert barrier_layout(config) != barrier_layout(other)


def test_start_cells_are_never_barriered(config):
    layout = barrier_layout(config)

    assert tuple(config.cop_start) not in layout
    assert tuple(config.thief_start) not in layout


def test_every_barrier_is_on_the_board(config):
    for row, col in barrier_layout(config):
        assert 0 <= row < config.grid_size
        assert 0 <= col < config.grid_size


def test_a_null_seed_means_a_bare_board(config):
    """One key controls activation AND layout, so they cannot fall out of step."""
    assert barrier_layout(replace(config, barrier_seed=None)) == frozenset()


def test_the_free_space_stays_connected(config):
    """A walled-off region would make capture arbitrary rather than skilful."""
    layout = barrier_layout(config)

    assert _free_space_is_connected(config, layout)


def test_connectivity_holds_across_many_seeds(config):
    """The resample must be a real guarantee, not luck on one seed."""
    for seed in range(40):
        layout = barrier_layout(replace(config, barrier_seed=seed))
        assert len(layout) == config.max_barriers
        assert _free_space_is_connected(replace(config, barrier_seed=seed), layout)


def test_populated_board_carries_the_layout(config):
    """One factory for every construction site.

    ``run_local_mcp_match`` builds a Board for the CLIENTS' policy view that
    is a different object from each peer server's episode board. They agreed
    only while both were empty; a shared factory is what keeps the mask the
    policy reasons about equal to the board the engine resolves on.
    """
    from engine.barriers import populated_board

    board = populated_board(config)

    assert board.barrier_count == config.max_barriers
    assert all(board.is_barrier(cell) for cell in barrier_layout(config))


def test_populated_board_is_bare_under_a_null_seed(config):
    from engine.barriers import populated_board

    assert populated_board(replace(config, barrier_seed=None)).barrier_count == 0
