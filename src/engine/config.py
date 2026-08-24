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
    axis_origin_corner: str
    axis_start_index: int
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
    requests_per_minute: int
    concurrent_requests: int
    retry_backoff_sec: float
    max_retries: int
    queue_depth: int


# The convention this engine implements, in the contract's own vocabulary.
# `actions.py` computes N as (-1, 0) and `board.py` indexes from 0; a peer on
# any other convention plays a mirrored game that still looks plausible.
#
# The LEAGUE spells it with a hyphen and so do we now: the value sits inside
# the signed terms, `negotiate` compares those exactly, and every opposing
# group runs the community kit -- which writes `top-left` in all five places
# it appears. Our old `topleft` refused all of them on a hyphen.
SUPPORTED_AXIS_ORIGIN = "top-left"
# Accepted spellings of that SAME corner. Two strings, one geometry: a
# contract written either way runs unchanged. A different CORNER is not on
# this list and never should be -- that peer plays a mirrored game.
AXIS_ORIGIN_ALIASES = frozenset({"top-left", "topleft"})
SUPPORTED_AXIS_START = 0


def _validate_axis(board: dict) -> None:
    """Refuse a coordinate convention this engine does not implement.

    Raises:
        ValueError: the contract names an origin or start index we would
            silently disagree with rather than fail on.
    """
    if board["axis_origin_corner"] not in AXIS_ORIGIN_ALIASES:
        raise ValueError(
            f"axis_origin_corner is {board['axis_origin_corner']!r}; this "
            f"engine implements the top-left origin only, spelled "
            f"{sorted(AXIS_ORIGIN_ALIASES)}. Playing on a different origin "
            "would mirror every move and produce a plausible but wrong game "
            "rather than an error."
        )
    if board["axis_start_index"] != SUPPORTED_AXIS_START:
        raise ValueError(
            f"axis_start_index is {board['axis_start_index']!r}; this engine "
            f"indexes from {SUPPORTED_AXIS_START}. Playing on a different "
            "origin would mirror every coordinate rather than fail."
        )


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

    _validate_axis(data["board_and_agents"])

    return GameConfig(
        grid_size=data["board_and_agents"]["grid_size"],
        cop_start=data["board_and_agents"]["cop_start"],
        thief_start=data["board_and_agents"]["thief_start"],
        move_set=data["movement_and_barriers"]["move_set"],
        max_barriers=data["movement_and_barriers"]["max_barriers"],
        axis_origin_corner=data["board_and_agents"]["axis_origin_corner"],
        axis_start_index=data["board_and_agents"]["axis_start_index"],
        # OPTIONAL extension: absent means a bare board, which is what a
        # peer that never heard of it will play. Required would make the
        # agreed 1.2 schema unloadable and lose a match before turn 0.
        barrier_seed=data["movement_and_barriers"].get("barrier_seed"),
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
        requests_per_minute=data["rate_limiter_gatekeeper"]["requests_per_minute"],
        concurrent_requests=data["rate_limiter_gatekeeper"]["concurrent_requests"],
        retry_backoff_sec=data["rate_limiter_gatekeeper"]["retry_backoff_sec"],
        max_retries=data["rate_limiter_gatekeeper"]["max_retries"],
        queue_depth=data["rate_limiter_gatekeeper"]["queue_depth"],
    )
