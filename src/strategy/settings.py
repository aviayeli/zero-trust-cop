"""Private per-peer strategy tunables, separate from shared ``game.json``.

Every strategy field is required: missing configuration must fail loudly rather
than silently training with invented defaults.
"""

from dataclasses import dataclass
import os
import tomllib


_DEFAULT_CONFIG_ROOT = "config"
_CONFIG_FILENAME = "game.toml"


@dataclass(frozen=True)
class StrategySettings:
    learning_rate: float
    discount_factor: float
    exploration_rate: float
    initial_q_value: float
    invalid_move_penalty: float
    qtable_path: str


def strategy_settings_path(role: str, config_root: str | None = None) -> str:
    """Build the private strategy path for one peer."""
    if config_root is None:
        config_root = os.environ.get("ZTC_CONFIG_ROOT", _DEFAULT_CONFIG_ROOT)
    return os.path.join(config_root, role, _CONFIG_FILENAME)


def load_strategy_settings(
    role: str, config_root: str | None = None
) -> StrategySettings:
    """Load all required private strategy settings for one peer."""
    with open(strategy_settings_path(role, config_root), "rb") as config_file:
        strategy = tomllib.load(config_file)["strategy"]
    return StrategySettings(
        learning_rate=strategy["learning_rate"],
        discount_factor=strategy["discount_factor"],
        exploration_rate=strategy["exploration_rate"],
        initial_q_value=strategy["initial_q_value"],
        invalid_move_penalty=strategy["invalid_move_penalty"],
        qtable_path=strategy["qtable_path"],
    )
