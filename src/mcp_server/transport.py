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


# A wildcard bind means "every interface"; it names no host to connect TO.
# Translating it is what lets a peer be exposed for league play without
# redirecting our own client at an address that is not a destination.
_WILDCARD_DIAL = {"0.0.0.0": "127.0.0.1", "": "127.0.0.1", "::": "::1"}


def dial_host(bound_host: str) -> str:
    """The address a CLIENT should connect to for a peer bound at ``bound_host``."""
    return _WILDCARD_DIAL.get(bound_host, bound_host)


@dataclass(frozen=True)
class NetworkSettings:
    """One peer's listener binding and its opponent's endpoint."""

    host: str
    my_port: int
    opponent_url: str
    # Required, and deliberately without a default: a poll interval is a
    # tunable, and a literal here would be exactly the hardcoded
    # hyperparameter the [network] block exists to avoid.
    poll_interval_sec: float
    public_url: str = ""
    # The one port both our roles share when served unified (PRD_11b).
    # Defaulted, because a workspace written before that phase has no such
    # key and must still load -- the split-port topology is the default.
    unified_port: int = 0

    @property
    def dial_host(self) -> str:
        """Where to reach this peer locally, whatever interface it binds."""
        return dial_host(self.host)


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
        poll_interval_sec=network["poll_interval_sec"],
        public_url=parse_public_url(network.get("public_url", "")),
        unified_port=network.get("unified_port", 0),
    )
