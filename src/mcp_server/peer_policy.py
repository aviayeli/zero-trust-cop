"""Build a peer's AgentPolicy from its private strategy configuration.

Match play is GREEDY (D5). The trained tables carry a residual epsilon of
~0.0135 after 2000 decayed games, so a peer reusing its TRAINING settings
would still play a random move roughly one turn in seventy-four — spending
points in a scored series to sample moves it already has values for. The rate
comes from the private ``match_exploration_rate`` key rather than a literal,
so it stays tunable without editing Python.

Every failure here is loud. A peer that starts, looks trained, and plays from
nothing is the worst available outcome: it would silently pick the first move
in ``move_set`` every turn and still report a healthy match status.
"""

from dataclasses import replace

from agent.agent_core import AgentPolicy
from strategy.belief import BeliefTracker
from strategy.pheromones import PheromoneField
from strategy.qvalues import QValues
from strategy.settings import load_strategy_settings


def build_peer_policy(peer_role, engine_role, config, config_root=None):
    """Build one peer's greedy, table-backed policy.

    Args:
        peer_role: config directory name — "police" or "thief".
        engine_role: engine vocabulary — "cop" or "thief". Not the same thing.

    Raises:
        FileNotFoundError: the configured qtable_path does not exist.
        ValueError: the table's state layout version differs, or it is empty.
    """
    settings = load_strategy_settings(peer_role, config_root)
    match_settings = replace(
        settings, exploration_rate=settings.match_exploration_rate
    )

    qvalues = QValues(config, match_settings)
    qvalues.load()
    if not qvalues.q_table:
        raise ValueError(
            f"{peer_role} loaded an EMPTY Q-table from "
            f"{match_settings.qtable_path}; it would play untrained"
        )

    return AgentPolicy(
        engine_role,
        config,
        match_settings,
        qvalues,
        PheromoneField(config),
        BeliefTracker(config, match_settings),
    )
