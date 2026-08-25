"""Tests for new private strategy settings: epsilon decay and training params."""

import pytest

from strategy.settings import load_strategy_settings

_EXPECTED = {
    "epsilon_decay_factor": 0.999744,
    "epsilon_floor": 0.01,
    "num_games": 2000,
    "hint_max_words": 15,
}


@pytest.mark.parametrize("role", ["police", "thief"])
def test_four_new_settings_load_with_configured_values(role):
    """Both roles carry the four new keys with their configured VALUES, not just names."""
    settings = load_strategy_settings(role)
    for key, expected in _EXPECTED.items():
        assert getattr(settings, key) == expected


def test_epsilon_decay_factor_is_float():
    """epsilon_decay_factor loads as a float."""
    settings = load_strategy_settings("police")
    assert isinstance(settings.epsilon_decay_factor, float)


def test_epsilon_floor_is_float():
    """epsilon_floor loads as a float."""
    settings = load_strategy_settings("police")
    assert isinstance(settings.epsilon_floor, float)


def test_num_games_is_int():
    """num_games loads as an int."""
    settings = load_strategy_settings("police")
    assert isinstance(settings.num_games, int)


def test_hint_max_words_is_int():
    """hint_max_words loads as an int."""
    settings = load_strategy_settings("police")
    assert isinstance(settings.hint_max_words, int)


def test_missing_epsilon_decay_factor_raises_key_error(tmp_path):
    """Missing epsilon_decay_factor key raises KeyError, no default."""
    role_dir = tmp_path / "police"
    role_dir.mkdir()
    (role_dir / "game.toml").write_text(
        """[strategy]
learning_rate = 0.1
discount_factor = 0.9
exploration_rate = 0.1
initial_q_value = 0.0
invalid_move_penalty = -1.0
honesty_prior = 0.5
qtable_path = "qtable.json"
epsilon_floor = 0.01
num_games = 2000
hint_max_words = 15
"""
    )
    with pytest.raises(KeyError):
        load_strategy_settings("police", config_root=str(tmp_path))


def test_qtable_path_differs_between_roles():
    """Verify qtable_path values still differ between police and thief."""
    police = load_strategy_settings("police")
    thief = load_strategy_settings("thief")
    assert police.qtable_path != thief.qtable_path


@pytest.mark.parametrize("role", ["police", "thief"])
def test_step_cost_loads_as_a_small_negative_float(role):
    """The living penalty is configured PER PEER, never inlined in the trainer.

    The two roles now differ (-0.1 for the pursuer, -0.05 for the evader), so
    a single expected value would pin one peer and silently ignore the other.
    """
    settings = load_strategy_settings(role)
    assert -1.0 < settings.step_cost < 0.0
    assert isinstance(settings.step_cost, float)


@pytest.mark.parametrize("role", ["police", "thief"])
def test_step_cost_is_dwarfed_by_every_terminal_payoff(role):
    """Shaping must nudge the policy, never rewrite the payoff matrix."""
    settings = load_strategy_settings(role)
    assert abs(settings.step_cost) < abs(settings.invalid_move_penalty)


@pytest.mark.parametrize("role", ["police", "thief"])
def test_match_exploration_rate_loads_as_a_float(role):
    """D5: match play is greedy, and the rate is configured, not hardcoded."""
    settings = load_strategy_settings(role)
    assert settings.match_exploration_rate == 0.0
    assert isinstance(settings.match_exploration_rate, float)
