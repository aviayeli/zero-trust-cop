"""Where a peer binds, and where it reaches its opponent.

These are tunables, so they live in the peer's private ``game.toml`` under
the canonical ``[network]`` block rather than as literals in Python. The shared
``config/game.json`` stays untouched: binding is a local deployment concern,
not part of the Step-0 contract between the two groups.

Every key is required. A half-configured peer that silently fell back to a
default port would bind somewhere its opponent is not calling.
"""

from dataclasses import dataclass
import tomllib

from mcp_server.tunnel import parse_public_url
from strategy.settings import strategy_settings_path


@dataclass(frozen=True)
class NetworkSettings:
    """One peer's listener binding and its opponent's endpoint."""

    host: str
    my_port: int
    opponent_url: str
    public_url: str = ""


def load_network_settings(
    role: str, config_root: str | None = None
) -> NetworkSettings:
    """Load one peer's [network] block, failing loudly on any missing key."""
    with open(strategy_settings_path(role, config_root), "rb") as config_file:
        network = tomllib.load(config_file)["network"]
    return NetworkSettings(
        host=network["host"],
        my_port=network["my_port"],
        opponent_url=network["opponent_url"],
        public_url=parse_public_url(network.get("public_url", "")),
    )
