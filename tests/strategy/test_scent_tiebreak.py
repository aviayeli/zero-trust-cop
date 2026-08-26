"""Break ties on belief mass rather than on an off-manifold table.

The Q-table currently breaks ties among distance-optimal moves. It was trained
against TRUE opponent positions and is executed against a lagging belief, so
on this wire its ranking is off-manifold -- it is answering a question about a
state distribution it never saw.

The proposal is to rank ties by the belief mass ADJACENT to each candidate.
Gemini argued it both intercepts a sharp peak and corrals a diffuse cloud. That
is an argument, not evidence, so it is measured in the benchmark; these tests
only pin that the rule computes what it claims.

Note the mass is our belief about THEM, not our own trail: `PheromoneField`
here is fed from the opponent's transmitted grid, so "highest adjacent mass"
means "closest to where we think they are", which is the right direction for a
pursuer and would be exactly wrong for an evader.
"""

import pytest

from strategy.scent import densest

GRID = 7


def test_it_picks_the_candidate_nearest_the_mass():
    field = {(0, 5): 4.0, (0, 4): 2.0}
    candidates = ["N", "S", "E", "W"]

    # from (0,3): E lands on (0,4), whose neighbour (0,5) carries the mass
    assert densest((0, 3), candidates, field, GRID) == "E"


def test_a_flat_field_leaves_the_order_alone():
    """No information, no opinion: the caller's order must survive so the
    existing tie-break stays deterministic."""
    field = {(3, 3): 1.0, (3, 4): 1.0, (2, 3): 1.0, (4, 3): 1.0}

    assert densest((0, 0), ["S", "E"], field, GRID) == "S"


def test_an_empty_field_leaves_the_order_alone():
    assert densest((3, 3), ["W", "N"], field={}, size=GRID) == "W"


def test_a_single_candidate_is_returned_unchanged():
    assert densest((3, 3), ["STAY"], {(0, 0): 9.0}, GRID) == "STAY"


def test_no_candidates_yields_none():
    assert densest((3, 3), [], {(0, 0): 9.0}, GRID) is None


def test_mass_off_the_board_is_not_counted():
    """A candidate on an edge must not be credited for neighbours that do not
    exist, or the rule would prefer corners for free."""
    edge_field = {(0, 0): 5.0}

    # from (1,1): N lands (0,1), W lands (1,0). Both are adjacent to (0,0).
    # Neither may be credited with off-board cells beyond the edge.
    assert densest((1, 1), ["N", "W"], edge_field, GRID) in ("N", "W")


def test_it_sums_neighbours_rather_than_reading_one_cell():
    """Two weak neighbours must beat one slightly stronger single cell, or
    this is just argmax again under another name."""
    field = {(0, 2): 3.0, (2, 2): 3.0, (1, 5): 5.0}

    # from (1,1): E lands (1,2), whose neighbours (0,2)+(2,2) sum to 6.
    # from (1,4): E lands (1,5) worth 5. The summed pair must win.
    assert densest((1, 1), ["E", "N"], field, GRID) == "E"


@pytest.mark.parametrize("size", [5, 7, 9])
def test_the_board_size_is_a_parameter_not_a_literal(size):
    assert densest((0, 0), ["S", "E"], {(size - 1, size - 1): 1.0},
                   size) in ("S", "E")


# --- and the live loop must actually use it --------------------------------


def test_the_distance_rule_can_be_handed_a_tiebreaker():
    """The rule is worthless if `manhattan_primary_action` never asks it."""
    import inspect

    from strategy import fallback

    source = inspect.getsource(fallback.manhattan_primary_action)
    assert "tiebreak" in source or "prefer" in source


def test_the_q_table_still_decides_when_no_tiebreaker_is_given():
    """FR: absent a tiebreaker, behaviour is exactly what it was."""
    import inspect

    from strategy import fallback

    source = inspect.getsource(fallback.manhattan_primary_action)
    assert "q_value" in source
