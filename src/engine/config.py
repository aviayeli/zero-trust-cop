"""Configuration management for the game engine."""

import json
from dataclasses import dataclass


@dataclass
class GameConfig:
    """Dataclass holding game configuration parameters."""

    grid_size: int
    cop_start: list
    thief_start: list
    move_set: list
    max_barriers: int
    barrier_seed: int | None
    max_moves: int
    survival_threshold: int
    response_timeout_sec: int
    watchdog_timeout_sec: int
    pheromone_center_intensity: float
    pheromone_decay: float
    pheromone_grid_size: int
    capture_cop: int
    capture_thief: int
    survival_cop: int
    survival_thief: int
    tie_score: int
    technical_loss: int


def load_config(path: str) -> GameConfig:
    """Load game configuration from a JSON file.

    Args:
        path: Path to the configuration JSON file.

    Returns:
        GameConfig instance populated from the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
        KeyError: If a required key is missing from the JSON structure.
    """
    with open(path, "r") as f:
        data = json.load(f)

    return GameConfig(
        grid_size=data["board_and_agents"]["grid_size"],
        cop_start=data["board_and_agents"]["cop_start"],
        thief_start=data["board_and_agents"]["thief_start"],
        move_set=data["movement_and_barriers"]["move_set"],
        max_barriers=data["movement_and_barriers"]["max_barriers"],
        barrier_seed=data["movement_and_barriers"]["barrier_seed"],
        max_moves=data["movement_and_barriers"]["max_moves"],
        survival_threshold=data["movement_and_barriers"]["survival_threshold"],
        response_timeout_sec=data["network_and_league"]["response_timeout_sec"],
        watchdog_timeout_sec=data["network_and_league"]["watchdog_timeout_sec"],
        pheromone_center_intensity=data["pheromones"]["pheromone_center_intensity"],
        pheromone_decay=data["pheromones"]["pheromone_decay"],
        pheromone_grid_size=data["pheromones"]["pheromone_grid_size"],
        capture_cop=data["scoring"]["capture_cop"],
        capture_thief=data["scoring"]["capture_thief"],
        survival_cop=data["scoring"]["survival_cop"],
        survival_thief=data["scoring"]["survival_thief"],
        tie_score=data["scoring"]["tie_score"],
        technical_loss=data["scoring"]["technical_loss"],
    )
