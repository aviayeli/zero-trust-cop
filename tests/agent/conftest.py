"""Pytest configuration for agent tests."""

import pytest

from engine.config import GameConfig
from strategy.belief import BeliefTracker
from strategy.pheromones import PheromoneField
from strategy.qvalues import QValues
from strategy.settings import StrategySettings


@pytest.fixture
def game_config():
    """Real GameConfig for a 7x7 board."""
    return GameConfig(
        grid_size=7,
        cop_start=[0, 0],
        thief_start=[6, 6],
        move_set=["N", "S", "E", "W", "STAY"],
        max_barriers=10,
        barrier_seed=None,
        max_moves=35,
        survival_threshold=30,
        response_timeout_sec=5,
        watchdog_timeout_sec=10,
        pheromone_center_intensity=1.0,
        pheromone_decay=0.1,
        pheromone_grid_size=5,
        capture_cop=20,
        capture_thief=5,
        survival_cop=5,
        survival_thief=10,
        tie_score=2,
        technical_loss=0,
    )


@pytest.fixture
def strategy_settings(game_config):
    """Real StrategySettings."""
    return StrategySettings(
        learning_rate=0.1,
        discount_factor=0.9,
        exploration_rate=0.1,
        initial_q_value=0.0,
        invalid_move_penalty=-1.0,
        step_cost=-0.01,
        honesty_prior=0.5,
        qtable_path="/tmp/q_table.json",
        epsilon_decay_factor=0.995,
        epsilon_floor=0.01,
        num_games=6,
        hint_max_words=15,
        match_exploration_rate=0.0,
        policy_mode="qtable_primary",
    )


@pytest.fixture
def qvalues(game_config, strategy_settings):
    """Real QValues instance."""
    return QValues(game_config, strategy_settings)


@pytest.fixture
def pheromones(game_config):
    """Real PheromoneField instance."""
    return PheromoneField(game_config)


@pytest.fixture
def belief(game_config, strategy_settings):
    """Real BeliefTracker instance."""
    return BeliefTracker(game_config, strategy_settings)
