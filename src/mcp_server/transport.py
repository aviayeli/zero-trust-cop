"""Where a peer binds its MCP listener (D1: streamable HTTP on local ports).

Host and port are tunables, so they live in the peer's private ``game.toml``
under ``[transport]`` rather than as literals in Python. The shared
``config/game.json`` stays untouched: binding is a local deployment concern,
not part of the Step-0 contract between the two groups.

Every key is required. A half-configured peer that silently fell back to a
default port would bind somewhere its opponent is not calling.
"""

from dataclasses import dataclass
import tomllib

from strategy.settings import strategy_settings_path


@dataclass(frozen=True)
class TransportSettings:
    """One peer's listener binding."""

    host: str
    port: int


def load_transport_settings(
    role: str, config_root: str | None = None
) -> TransportSettings:
    """Load one peer's [transport] block, failing loudly on any missing key."""
    with open(strategy_settings_path(role, config_root), "rb") as config_file:
        transport = tomllib.load(config_file)["transport"]
    return TransportSettings(host=transport["host"], port=transport["port"])
