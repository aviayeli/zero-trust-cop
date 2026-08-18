"""PLAN.md §10.10's provenance claim must stay true (it did not).

The section stated that the flagship log's trajectory "remains exactly what
today's policy produces". That was true while the board was bare. Phase 9
placed a barrier on `(1, 1)` — the cop's turn-1 cell in that log — so the
shipped policy now plays a different, longer pursuit, and the sentence became
false with nothing to catch it.

The lesson is the one this repository already applies to the README and to
§10.10's capture-rate table: a document making an exact claim gets a
mechanical check, or it quietly rots. So the relationship between the sealed
artifacts and the current policy is re-derived here rather than asserted in
prose.
"""

import json
from dataclasses import replace
from pathlib import Path
from random import Random

import pytest

from engine.config import load_config
from engine.game_loop import GameEpisode
from mcp_server.peer_policy import build_peer_policy

PLAN = Path("docs/PLAN.md")
SHIPPED_LOG = Path("logs/aviayeli/log_aviayeli_g01.json")


def _pursue(config):
    """Replay the shipped policy from the published starts, greedily."""
    cop = build_peer_policy("police", "cop", config)
    thief = build_peer_policy("thief", "thief", config)
    episode = GameEpisode(config)
    rng = Random(0)
    while not episode.is_terminated:
        cop_move, _ = cop.decide(
            cop.state_key(
                episode.cop_state.position, episode.thief_state.position, episode.board
            ),
            rng,
        )
        thief_move, _ = thief.decide(
            thief.state_key(
                episode.thief_state.position, episode.cop_state.position, episode.board
            ),
            rng,
        )
        episode.step(cop_move, thief_move)
    return episode


@pytest.fixture(scope="module")
def todays_pursuit():
    return _pursue(load_config("config/police/game.json"))


def test_the_shipped_policy_no_longer_reproduces_the_flagship_trajectory(
    todays_pursuit,
):
    """The divergence is real, and pinning it is what stops the prose drifting."""
    log = json.loads(SHIPPED_LOG.read_text(encoding="utf-8"))
    logged_turns = len(log["turns"])

    assert todays_pursuit.turn_count != logged_turns, (
        "the trajectories agree again — §10.10's provenance note must be "
        "rewritten to say so"
    )


def test_the_plan_states_todays_actual_outcome(todays_pursuit):
    """§10.10 must quote what today's policy does, not what it used to do.

    The log records a capture on turn 3. Phase 11 strengthened the evader,
    and from the SAME published starts the shipped cop no longer captures at
    all — the episode runs to the move limit. Quoting a "capture turn" here
    would itself be the stale claim this file exists to prevent.
    """
    captured = todays_pursuit.history[-1].result.captured
    plan = PLAN.read_text(encoding="utf-8")

    assert not captured, "the shipped cop captures again; §10.10 must be rewritten"
    assert f"runs to the {todays_pursuit.turn_count}-move limit" in plan


def test_the_sealed_artifacts_are_still_the_record_of_a_real_match():
    """Divergence must not be read as the evidence being invalid."""
    log = json.loads(SHIPPED_LOG.read_text(encoding="utf-8"))

    assert log["turns"], "the flagship log is empty"
    assert log["turns"][-1]["result"]["captured"] is True


def test_the_divergence_is_caused_by_the_retrain_not_the_barriers(todays_pursuit):
    """§10.10 attributes the drift to the retrain, and that was NOT obvious.

    The intuitive reading is that §4.3 walls the log's turn-1 cell (1, 1) and
    so forces a different route. Measurement says otherwise: replayed on a
    BARE board, today's tables produce the same turn count, so the wall is
    incidental and the learned values are the cause. The first draft of this
    section asserted the intuitive version and was wrong, which is why the
    claim is pinned rather than reasoned.
    """
    bare = replace(load_config("config/police/game.json"), barrier_seed=None)

    assert _pursue(bare).turn_count == todays_pursuit.turn_count, (
        "the bare and barriered boards now diverge — §10.10's causal claim "
        "must be re-derived"
    )
