"""The two team repositories, declared once in config and read everywhere.

Both URLs belong in every submission artifact so a marker holding either half
of the pair can find the other. They live in each peer's ``game.toml`` under
``[game.repos]`` rather than in ``config/game.json``, which is the shared
Step-0 contract and stays untouched.
"""

import tomllib

from strategy.settings import strategy_settings_path

PEER_KEYS = ("cop", "thief")


def load_repos(role: str = "police", config_root: str | None = None) -> dict:
    """Both repository URLs, failing loudly if either is missing."""
    with open(strategy_settings_path(role, config_root), "rb") as config_file:
        repos = tomllib.load(config_file)["game"]["repos"]
    return {key: repos[key] for key in PEER_KEYS}


def load_email_settings(role: str = "police", config_root: str | None = None) -> dict:
    """The peer's private [email] block: where the report goes, and how."""
    with open(strategy_settings_path(role, config_root), "rb") as config_file:
        settings = tomllib.load(config_file)["email"]
    return {"recipient": settings["recipient"], "mode": settings["mode"]}
