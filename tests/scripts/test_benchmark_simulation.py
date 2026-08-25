"""The harness must measure the thing it claims to (PRD_19 FR1, FR5).

A benchmark is only worth its weakest assumption. Two could invalidate every
number it prints: that the cop's belief really comes from a transmitted grid
rather than a true position, and that a seed really reproduces a run. Both are
asserted here rather than assumed.
"""

import pytest

from scripts.benchmark_simulation import benchmark
from scripts.thief_profiles import PROFILES, deceptive_bluffer


def test_all_four_profiles_are_measured():
    assert set(PROFILES) == {"A_random", "B_greedy", "C_bluffer", "D_corner"}


def test_the_bluffer_transmits_a_cell_it_is_not_on():
    """Profile C's whole point: what it sends and where it is come apart."""
    from engine.barriers import populated_board
    from engine.config import load_config

    config = load_config("config/game.json")
    board = populated_board(config)
    landed, faked = deceptive_bluffer(board, (3, 3), (0, 0), None,
                                      config.grid_size)

    assert faked == (config.grid_size - 1, config.grid_size - 1)
    assert landed != faked, "the bluff must not accidentally be the truth"


def test_the_honest_profiles_transmit_where_they_are():
    from engine.barriers import populated_board
    from engine.config import load_config

    config = load_config("config/game.json")
    board = populated_board(config)
    for name in ("A_random", "B_greedy", "D_corner"):
        import random
        _, faked = PROFILES[name](board, (3, 3), (0, 0), random.Random(1),
                                  config.grid_size)
        assert faked is None, f"{name} should not fake its grid"


@pytest.mark.parametrize("arm", ["thawed", "unthawed"])
def test_a_seed_reproduces_a_run(arm):
    """FR5: a reported figure that cannot be reproduced is an anecdote."""
    first = benchmark(games=3, seed=7)
    again = benchmark(games=3, seed=7)

    assert first["C_bluffer"][arm] == again["C_bluffer"][arm]


def test_the_unthawed_arm_still_freezes_against_the_bluffer():
    """The baseline must reproduce the defect, or the comparison is empty."""
    report = benchmark(games=6, seed=11)

    assert report["C_bluffer"]["unthawed"]["longest_stay_run"] > 3


def test_the_thawed_arm_does_not():
    report = benchmark(games=6, seed=11)
    from strategy.settings import load_strategy_settings

    bound = load_strategy_settings("police").max_consecutive_stay
    assert report["C_bluffer"]["thawed"]["longest_stay_run"] <= bound
