"""Scripted training opponents, and the guarantee that they never learn.

Self-play against one adversary produced tables that a heuristic pursuer
exploits — the shipped evader survived 2.2% where an EMPTY table survived
69.8% (PLAN.md §10.10). The remedy is a pool of opponents that do not
co-evolve with us.

None of these is a new algorithm. A greedy Manhattan evader is already
expressible as an `AgentPolicy` carrying an empty table under
`manhattan_primary`; an interceptor is the same object with the cop's role; a
random mover is `exploration_rate = 1.0`. Building them any other way would
mean a second implementation of the movement rules, free to drift out of step
with `strategy/fallback.py`.

What IS new is `frozen`: a scripted opponent must never update a table, or it
stops being the fixed reference the pool exists to provide.
"""

from random import Random

import pytest

from engine.board import Board
from engine.config import load_config
from strategy.opponents import frozen, random_mover, scripted


@pytest.fixture
def config():
    return load_config("config/game.json")


@pytest.fixture
def board(config):
    return Board(config)


def test_a_scripted_evader_maximises_distance(config, board):
    """Opponent due north: the evader must go south."""
    evader = scripted(config, "thief")
    state = evader.state_key((3, 3), (1, 3), board)

    assert evader.decide(state, Random(0))[0] == "S"


def test_a_scripted_interceptor_minimises_distance(config, board):
    interceptor = scripted(config, "cop")
    state = interceptor.state_key((3, 3), (5, 3), board)

    assert interceptor.decide(state, Random(0))[0] == "S"


def test_a_random_mover_does_not_always_choose_the_same_action(config, board):
    mover = random_mover(config, "thief")
    state = mover.state_key((3, 3), (1, 3), board)
    chosen = {mover.decide(state, Random(seed))[0] for seed in range(30)}

    assert len(chosen) > 1, "a random opponent that never varies is not random"


def test_a_frozen_policy_refuses_to_learn(config, board):
    """The whole point: a fixed reference cannot co-evolve with us."""
    opponent = frozen(scripted(config, "thief"))
    state = opponent.state_key((3, 3), (1, 3), board)

    opponent.learn(state, "S", 20.0, state, True)

    assert opponent.qvalues.q_table == {}


def test_a_frozen_policy_still_decides_and_observes(config, board):
    """Freezing disables learning only, not the rest of the interface."""
    opponent = frozen(scripted(config, "thief"))
    state = opponent.state_key((3, 3), (1, 3), board)

    assert opponent.decide(state, Random(0))[0] == "S"
    opponent.observe_opponent("cop", "north", "N", (1, 3))


def test_a_frozen_policy_exposes_the_settings_the_loop_needs(config):
    """`play_episode` reads settings and qvalues off both sides."""
    opponent = frozen(scripted(config, "cop"))

    assert opponent.settings.invalid_move_penalty
    assert opponent.qvalues.reward("cop", "capture") == config.capture_cop


def test_scripted_opponents_carry_no_learned_values(config):
    """A scripted opponent is the RULE, not a table someone trained."""
    assert scripted(config, "cop").qvalues.q_table == {}
    assert random_mover(config, "thief").qvalues.q_table == {}
