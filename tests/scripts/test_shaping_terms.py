"""The two per-turn shaping terms, tested directly on ``shaping_reward``.

Terminal-only rewards left the learner unable to tell a wasted turn from a
useful one: bumping the north wall and advancing toward the thief were worth
exactly the same (zero), which is how a degenerate "always N" policy survives
2000 training games. These two terms are the whole fix, and both are read from
the peer's private ``[strategy]`` block rather than inlined here.

The series-level consequences live in ``test_shaped_rewards.py``.
"""

import pytest

from scripts.tournament_loop import shaping_reward


@pytest.fixture
def settings(training_settings):
    """One peer's real settings, without running a training series."""
    cop, _ = training_settings(num_games=1)
    return cop


def test_a_blocked_move_pays_the_configured_invalid_move_penalty(settings):
    """Position unchanged after a non-STAY move means a wall refused it."""
    reward = shaping_reward(settings, "N", (0, 0), (0, 0), captured=False)

    assert reward == settings.invalid_move_penalty + settings.step_cost


def test_staying_put_on_purpose_is_not_an_invalid_move(settings):
    """STAY is a legal choice; only a REFUSED move is penalised."""
    reward = shaping_reward(settings, "STAY", (0, 0), (0, 0), captured=False)

    assert reward == settings.step_cost


def test_a_move_that_actually_moved_pays_only_the_living_penalty(settings):
    reward = shaping_reward(settings, "N", (3, 3), (2, 3), captured=False)

    assert reward == settings.step_cost


def test_a_capture_turn_pays_no_living_penalty(settings):
    """The living penalty exists to shorten the path, not to tax arriving."""
    reward = shaping_reward(settings, "N", (3, 3), (2, 3), captured=True)

    assert reward == 0.0


def test_a_blocked_move_is_still_penalised_on_the_capture_turn(settings):
    reward = shaping_reward(settings, "N", (0, 0), (0, 0), captured=True)

    assert reward == settings.invalid_move_penalty


def test_the_living_penalty_cannot_outweigh_the_terminal_signal(config, settings):
    """A whole match of shaping must stay small against the smallest payoff."""
    worst = abs(settings.step_cost) * config.max_moves

    assert worst < min(config.capture_thief, config.survival_cop)
