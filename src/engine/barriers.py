"""Derive the board's barrier layout from shared configuration (PLAN.md §4.3).

The layout is DERIVED, never exchanged.  Both peers load the same shared
``game.json``, so both build the identical board without a wire message —
a transmitted layout would be one more thing a hostile peer could lie about,
and one more way the two mirrored engines could diverge (PLAN.md §2).

``barrier_seed: null`` yields a bare board.  One key controls both activation
and layout, so there is no separate boolean to fall out of step with it.

CONFIGURED CONSTANTS (``config/game.json``, never literals here):
``max_barriers`` and ``barrier_seed``.
"""

import random

from engine.board import Board

_NEIGHBOUR_DELTAS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def _candidate_cells(config) -> list:
    """Every cell an agent does not start on, in a stable order.

    Start cells are excluded before sampling rather than rejected after, so
    no agent can begin inside a wall and the sample size stays exact.
    """
    starts = {tuple(config.cop_start), tuple(config.thief_start)}
    return [
        (row, col)
        for row in range(config.grid_size)
        for col in range(config.grid_size)
        if (row, col) not in starts
    ]


def _is_connected(config, layout: frozenset) -> bool:
    """Whether every non-barrier cell is reachable from ``cop_start``.

    A random scatter can wall a region off entirely, which would make capture
    an artefact of the layout rather than of play.
    """
    size = config.grid_size
    start = tuple(config.cop_start)
    seen = {start}
    frontier = [start]
    while frontier:
        row, col = frontier.pop()
        for delta_row, delta_col in _NEIGHBOUR_DELTAS:
            cell = (row + delta_row, col + delta_col)
            if not (0 <= cell[0] < size and 0 <= cell[1] < size):
                continue
            if cell in layout or cell in seen:
                continue
            seen.add(cell)
            frontier.append(cell)
    return len(seen) == size * size - len(layout)


def barrier_layout(config) -> frozenset:
    """Return the configured barrier cells, or an empty set for a null seed.

    Resamples under a DETERMINISTIC counter until the free space is connected,
    so the retry costs reproducibility nothing: one config always yields one
    layout, however many attempts it took to find it.

    Raises:
        ValueError: no connected layout was found for this configuration.
    """
    if config.barrier_seed is None:
        return frozenset()
    candidates = _candidate_cells(config)
    if config.max_barriers > len(candidates):
        raise ValueError(
            f"max_barriers {config.max_barriers} exceeds the "
            f"{len(candidates)} cells no agent starts on"
        )
    for attempt in range(_MAX_ATTEMPTS):
        rng = random.Random(f"{config.barrier_seed}:{attempt}")
        layout = frozenset(rng.sample(candidates, config.max_barriers))
        if _is_connected(config, layout):
            return layout
    raise ValueError(
        f"no connected layout for seed {config.barrier_seed} "
        f"in {_MAX_ATTEMPTS} attempts"
    )


def populated_board(config) -> Board:
    """Build the board every play path should run on.

    A single factory because ``run_local_mcp_match`` constructs the CLIENTS'
    board separately from each peer server's episode board: two objects that
    agreed only while both were empty.
    """
    board = Board(config)
    for cell in barrier_layout(config):
        board.place_barrier(cell)
    return board


# Attempts before a configuration is declared unsatisfiable. Not a tunable:
# it bounds a search that succeeds within a handful of draws at 14/47, and
# exists so a pathological config fails loudly instead of looping forever.
_MAX_ATTEMPTS = 1000
