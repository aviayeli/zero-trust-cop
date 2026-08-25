"""The regression that matters: replay the frozen game and stay thawed.

`test_thaw` pins the rule in isolation. This drives it with the ACTUAL belief
trajectory from the graded sub-game that froze -- their real transmitted smell
grids, our real sealed positions -- and asserts the 16-turn run cannot recur.

A unit test of a rule I designed after the fact proves the rule does what I
said. Only the real trajectory proves it addresses what actually happened.
"""

import json

import pytest

from strategy.thaw import Thaw

GRADED = "logs/evidence/graded_series/log_aviayeli-vs-bb-ai-12_g01.json"


@pytest.fixture(scope="module")
def trajectory():
    """(our position, our belief) per step, rebuilt from the sealed log."""
    import sys

    sys.path.insert(0, "src")
    from engine.config import load_config
    from mcp_server.smell_reader import strongest_cell
    from strategy.pheromones import PheromoneField

    with open(GRADED) as handle:
        log = json.load(handle)
    field = PheromoneField(load_config("config/game.json"))
    out = []
    for turn in log["turns"]:
        payload = turn["ours"]["payload"]
        out.append((tuple(payload["position"]), field.strongest(),
                    payload["move"].replace("MOVE:", "")))
        theirs = strongest_cell((turn.get("theirs") or {}).get("smell_grid") or {})
        field.advance(deposits=[theirs] if theirs else [])
    return out


def test_the_real_game_really_did_freeze(trajectory):
    """Establish the baseline from the artifact before claiming a fix."""
    longest = run = 0
    for _, _, move in trajectory:
        run = run + 1 if move == "STAY" else 0
        longest = max(longest, run)

    assert longest == 16, f"expected the recorded 16-turn freeze, got {longest}"


def test_the_patched_rule_breaks_that_run(trajectory):
    """Replay the same beliefs; STAY must be forbidden before the run grows."""
    thaw = Thaw(role="cop", max_consecutive_stay=3)
    longest = run = 0

    for position, belief, _ in trajectory:
        forbidden = thaw.forbid(position=position, belief=belief)
        move = "N" if "STAY" in forbidden else "STAY"
        thaw.took(move, position=position)
        run = run + 1 if move == "STAY" else 0
        longest = max(longest, run)

    assert longest <= 3, f"still froze for {longest} turns"


def test_it_is_the_arrival_that_triggers_it_not_the_counter(trajectory):
    """The falsification fires the moment we stand on the belief -- step 12 in
    this game -- rather than waiting out a counter."""
    thaw = Thaw(role="cop", max_consecutive_stay=99)
    first = next(step for step, (position, belief, _)
                 in enumerate(trajectory, start=1)
                 if "STAY" in thaw.forbid(position=position, belief=belief))

    assert first == 12
