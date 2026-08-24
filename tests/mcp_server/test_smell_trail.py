"""The smell grid as it goes on the wire (PRD_10 FR6, revised 2026-08-24).

BOTH peers emit. ali-ahm1 confirmed the SPEC §5 wording — "each peer emits its
own" — and the cost of getting it wrong is one-sided: a cop that sends `{}`
gives its opponent no positional signal at all while receiving theirs in full,
which across a six-sub-game series with the sides swapping is an advantage to
whichever peer stayed silent. The field is required on every TurnMessage from
either sender, which is the same statement in the fixture's own vocabulary.

The kernel is CHEBYSHEV — a full 5x5 box, 25 cells — not the 13-cell Manhattan
diamond our internal belief field uses. Those are now genuinely two different
functions and the split is deliberate: `PheromoneField` is what WE believe and
is baked into the trained tables' state layout, while this is what we DISCLOSE
and is an inter-team term. Neither may quietly become the other.

Nothing here is sealed. `smell_grid` is not part of the committed payload, so
a kernel disagreement costs a difference in what each side learns — never a
false tamper verdict at audit.
"""

import pytest

from engine.config import load_config
from mcp_server.smell_trail import SmellTrail, strongest_cell
from mcp_server.wire_v3 import _is_smell_grid


@pytest.fixture
def config():
    return load_config("config/game.json")


@pytest.fixture
def trail(config):
    return SmellTrail(config)


def test_an_emitted_grid_is_wire_shaped(trail):
    trail.step((3, 3))

    grid = trail.grid()

    assert grid, "a deposited trail must not be empty"
    assert _is_smell_grid(grid), grid
    assert all(isinstance(value, float) for value in grid.values())
    assert "3,3" in grid


def test_the_kernel_is_a_full_chebyshev_box(trail):
    """25 cells, not the 13-cell Manhattan diamond. The twelve corners are the
    whole difference, and they are exactly what a diamond drops."""
    trail.step((3, 3))

    grid = trail.grid()

    assert len(grid) == 25
    assert "1,1" in grid and "5,5" in grid and "1,5" in grid and "5,1" in grid


def test_intensity_falls_off_by_chebyshev_distance(trail, config):
    """Emission alone. The exact published values are pinned against the
    kit's CORE vector in `test_pheromone_vectors.py`; this only fixes that a
    DIAGONAL is distance one, which is the whole difference from Manhattan."""
    trail.emit((3, 3))
    grid = trail.grid()

    assert grid["3,3"] == config.pheromone_center_intensity
    assert grid["4,4"] == grid["3,4"], "a diagonal is distance 1, same as an edge"
    assert grid["1,1"] < grid["3,4"]


def test_the_kernel_is_clipped_at_the_board_edge_never_wrapped(trail):
    trail.step((0, 0))

    grid = trail.grid()

    assert len(grid) == 9
    assert all(int(cell.split(",")[0]) >= 0 for cell in grid)


def test_a_single_deposit_points_at_the_cell_we_are_on(trail):
    trail.step((3, 3))

    assert strongest_cell(trail.grid()) == (3, 3)


def test_the_argmax_of_a_trail_names_where_that_peer_now_STANDS(trail):
    """This test used to assert the opposite, and the opposite was our bug.

    We merged emissions by SUM, so a revisited neighbour could tie or beat the
    current cell and we concluded the argmax meant "where they have been" —
    and told ali-ahm1 so. SPEC 5 merges by MAX: nothing exceeds
    `emit_intensity`, the freshest cell is strictly hottest, and the argmax
    does name where that peer is.
    """
    trail.step((3, 3))
    trail.step((3, 4))
    grid = trail.grid()

    assert grid["3,4"] == max(grid.values())
    assert grid["3,3"] < grid["3,4"]


def test_the_decay_is_subtractive_not_geometric(trail, config):
    """`subtractive_chebyshev_v1`, agreed with ali-ahm1 2026-08-24: a cell
    loses a FLAT `decay_per_step`, it is not scaled by `1 - decay_per_step`.

    The two readings of the term diverge slowly and never surface as an
    error: `smell_grid` is not sealed, so a mismatch costs a difference in
    what each side infers and can never be caught at audit. Our own
    `PheromoneField` keeps the geometric form — that one is our belief model,
    not a disclosure term.
    """
    trail.step((0, 0))
    fresh = trail.grid()["0,0"]
    trail.step((6, 6))

    assert trail.grid()["0,0"] == round(fresh - config.pheromone_decay, 3)
    assert trail.grid()["6,6"] == round(
        config.pheromone_center_intensity - config.pheromone_decay, 3)


def test_a_lone_deposit_is_retired_rather_than_fading_forever(trail, config):
    """Subtractive decay reaches zero; geometric decay never does. A peak of
    0.9 losing 0.1 a step is gone on the ninth, and the cell must LEAVE the
    grid rather than linger at 0.0 and be transmitted as a trace."""
    trail.step((0, 0))
    for _ in range(9):
        trail.step((6, 6))

    assert "0,0" not in trail.grid()


def test_a_cell_walked_twice_is_no_hotter_than_one_walked_once(trail):
    """The merge is by MAX and the ceiling is `emit_intensity`. We asserted
    the reverse — that revisits ADD — which is the divergence the kit's CORE
    vector catches and nothing we owned could."""
    trail.step((3, 3))
    once = trail.grid()["3,3"]
    trail.step((3, 3))

    assert trail.grid()["3,3"] == once
