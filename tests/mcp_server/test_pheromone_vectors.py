"""Conformance against the kit's CORE scent fixture (SPEC §5).

We shipped this wrong and did not know. Our vendored fixture set held 8 of the
kit's 15 and `pheromone.json` — a CORE tier vector — was one of the seven we
never took, so nothing could fail. ali-ahm1 named `subtractive_chebyshev_v1`
in a pre-match message and we told them it looked like an agreement rather
than a registration; it is §5, CORE, and the fixture was sitting in the repo
we had already vendored from.

Three divergences it catches, none of which any test we owned could see:

* the emitted field is merged into the trail by MAX, not summed. Summing lets
  a revisited cell exceed `center_intensity`, which is what made our own
  "the strongest cell is where they are now" reasoning come out as a tie.
* values round to 3 places, not to 12.
* `min_center_intensity` gates emission and we never read it.

SPEC §5 is explicit that this cannot void a game — scent is transmitted, not
re-derived cross-team — so it was never a tamper risk. It is a wrong belief
map and a trail the opponent's model does not predict.
"""

import json
from pathlib import Path

import pytest

from engine.config import load_config
from mcp_server.smell_trail import SmellTrail

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "interop" / "pheromone.json")
    .read_text(encoding="utf-8")
)
EMIT = FIXTURE["emit"]
DECAY = FIXTURE["decay"]


def _config(case):
    """The fixture's own parameters, not ours: a vector that ran on our
    contract's numbers would only prove we agree with ourselves."""
    from dataclasses import replace

    return replace(
        load_config("config/game.json"),
        grid_size=case["board_size"],
        pheromone_grid_size=case["grid_size"],
        pheromone_center_intensity=case["intensity"],
    )


def test_the_fixture_is_the_core_tier_one_we_missed():
    assert FIXTURE["status"] == "CORE"


@pytest.mark.parametrize("case", EMIT, ids=lambda c: c["note"][:40])
def test_one_emission_matches_the_published_field(case):
    trail = SmellTrail(_config(case))

    trail.emit(tuple(case["center"]))

    assert trail.grid() == case["field"]


@pytest.mark.parametrize("case", DECAY, ids=lambda c: c["note"][:40])
def test_one_step_of_decay_matches_the_published_field(case):
    from dataclasses import replace

    config = replace(load_config("config/game.json"),
                     pheromone_decay=case["decay"])
    trail = SmellTrail(config)
    trail.load({tuple(int(n) for n in cell.split(",")): value
                for cell, value in case["before"].items()})

    trail.decay()

    expected = {cell: value for cell, value in case["after"].items() if value > 0}
    assert trail.grid() == expected


def test_a_revisited_cell_never_exceeds_the_centre_intensity():
    """The merge is by MAX. Summing produced values above 0.9 — and with them
    a belief map the opponent's model cannot predict. A full turn emits and
    then decays, so the standing centre is 0.9 - 0.1."""
    trail = SmellTrail(load_config("config/game.json"))

    trail.step((3, 3))
    trail.step((3, 3))

    assert max(trail.grid().values()) == 0.8


def test_the_freshest_cell_is_the_strongest_after_a_walk():
    """What max-merge restores, and what summing broke: after stepping to a
    neighbour the new cell is strictly hottest, so the argmax of a received
    grid does name where that peer now stands."""
    trail = SmellTrail(load_config("config/game.json"))

    trail.step((3, 3))
    trail.step((3, 4))
    grid = trail.grid()

    assert grid["3,4"] == 0.8
    assert grid["3,3"] < grid["3,4"]


def test_ties_break_the_way_the_kit_breaks_them():
    """`hottest` in the kit orders ties lexicographically by (row, col).
    Iteration order is deterministic for us and different for them."""
    from mcp_server.smell_trail import strongest_cell

    assert strongest_cell({"5,5": 0.6, "1,2": 0.6, "3,3": 0.6}) == (1, 2)
