"""Fixed training opponents that do not co-evolve with the learner.

Self-play against a single adversary produced tables a heuristic pursuer
exploits: the shipped evader survived 2.2% where an EMPTY table survived 69.8%
(PLAN.md §10.10). Values learned that way encode ONE opponent's habits, so the
remedy is to train against opponents that cannot adapt to us.

None of these is a new movement algorithm, deliberately. A greedy Manhattan
evader is an ``AgentPolicy`` carrying an empty table under
``manhattan_primary``; an interceptor is the same object with the cop's role;
a random mover is ``exploration_rate = 1.0``. Re-deriving the rules here would
be a second implementation free to drift out of step with
``strategy/fallback.py`` — the module the shipped policy actually uses.

``frozen`` is the one real addition: a scripted opponent that quietly learned
would stop being the fixed reference the pool exists to provide.
"""

from dataclasses import replace

from agent.agent_core import AgentPolicy
from strategy.belief import BeliefTracker
from strategy.fallback import MANHATTAN_PRIMARY
from strategy.pheromones import PheromoneField
from strategy.qvalues import QValues
from strategy.settings import load_strategy_settings

# Which private workspace supplies the tunables for each engine role.
_WORKSPACE = {"cop": "police", "thief": "thief"}
_ALWAYS_EXPLORE = 1.0
_NEVER_EXPLORE = 0.0


def _policy(config, engine_role: str, exploration: float, config_root=None):
    """Build an AgentPolicy with an EMPTY table at a fixed exploration rate."""
    if engine_role not in _WORKSPACE:
        raise ValueError(f"unknown engine role: {engine_role!r}")
    settings = replace(
        load_strategy_settings(_WORKSPACE[engine_role], config_root),
        exploration_rate=exploration,
        policy_mode=MANHATTAN_PRIMARY,
    )
    return AgentPolicy(
        engine_role,
        config,
        settings,
        QValues(config, settings, role=engine_role),
        PheromoneField(config),
        BeliefTracker(config, settings),
    )


def scripted(config, engine_role: str, config_root=None) -> AgentPolicy:
    """A greedy distance opponent: evader for ``thief``, interceptor for ``cop``.

    The table is empty, so every state is flat and every decision falls to the
    distance rule — which maximises the gap for the thief and minimises it for
    the cop, from the SAME code the shipped policy consults.
    """
    return _policy(config, engine_role, _NEVER_EXPLORE, config_root)


def random_mover(config, engine_role: str, config_root=None) -> AgentPolicy:
    """A uniform random opponent: pure exploration, no preference at all."""
    return _policy(config, engine_role, _ALWAYS_EXPLORE, config_root)


class frozen:
    """Wrap a policy so it decides and observes but never updates its table.

    Delegation rather than a subclass: the learner and the opponents are the
    same class, and freezing is a property of this ROLE in training, not of
    the policy type.
    """

    def __init__(self, policy):
        self._policy = policy

    def __getattr__(self, name):
        return getattr(self._policy, name)

    def learn(self, state, action, reward, next_state, terminal) -> None:
        """Deliberately nothing: a fixed reference must stay fixed."""
