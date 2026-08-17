"""Offline batch trainer; drives GameEpisode directly, never the MCP transport.

MatchState's 2-slot buffer, its asyncio.Lock and its wall-clock timeouts exist
to reconcile two INDEPENDENT, ASYNCHRONOUS, EXTERNAL clients. Here both
policies are in-process and synchronous: the trainer already holds both moves,
no peer can be slow, and nothing is concurrent. Routing training through the
live protocol would add latency and failure modes while testing none of the
properties that protocol exists to guarantee (PLAN_05 Part B).
"""

import argparse
import os
import random

from agent.agent_core import AgentPolicy
from engine.config import load_config
from engine.game_loop import GameEpisode
from scripts.tournament_loop import play_episode
from strategy.belief import BeliefTracker
from strategy.pheromones import PheromoneField
from strategy.qvalues import QValues
from strategy.settings import load_strategy_settings

_DEFAULT_CONFIG_ROOT = "config"
_SHARED_CONFIG = "game.json"
_COP_CONFIG_DIR = "police"
_THIEF_CONFIG_DIR = "thief"


def build_policy(role, config, settings):
    """Assemble one peer's policy over its own private strategy objects.

    ``role`` is the ENGINE vocabulary ("cop"/"thief"), which is not the same
    as the config DIRECTORY name ("police"/"thief").
    """
    return AgentPolicy(
        role,
        config,
        settings,
        QValues(config, settings, role=role),
        PheromoneField(config),
        BeliefTracker(config, settings),
    )


def train_tournament(config, cop_settings, thief_settings, seed):
    """Train both peers and return the per-game (cop, thief) scores.

    The series length is read from each peer's PRIVATE [strategy] block, never
    from the shared game.json (D3), and never from the caller. Both RNGs are
    derived from ``seed`` alone, so a run is reproducible from that seed.
    """
    if cop_settings.num_games != thief_settings.num_games:
        raise ValueError(
            f"peers disagree on num_games: {cop_settings.num_games} "
            f"!= {thief_settings.num_games}"
        )

    master = random.Random(seed)
    rng_cop = random.Random(master.random())
    rng_thief = random.Random(master.random())

    cop = build_policy("cop", config, cop_settings)
    thief = build_policy("thief", config, thief_settings)
    episode = GameEpisode(config)

    scores = []
    for _ in range(cop_settings.num_games):
        scores.append(play_episode(episode, cop, thief, rng_cop, rng_thief))
        cop.qvalues.decay_epsilon()
        thief.qvalues.decay_epsilon()

    cop.qvalues.save()
    thief.qvalues.save()
    return scores


def _report(seed, config, cop_settings, thief_settings, scores):
    """Print the run summary, including the seed that reproduces it."""
    captures = sum(1 for cop_score, _ in scores if cop_score == config.capture_cop)
    print(f"seed={seed}")
    print(f"games={len(scores)}")
    print(f"captures={captures}")
    print(f"survivals={len(scores) - captures}")
    print(f"cop_total={sum(score[0] for score in scores)}")
    print(f"thief_total={sum(score[1] for score in scores)}")
    print(f"cop_table={cop_settings.qtable_path}")
    print(f"thief_table={thief_settings.qtable_path}")


def main(argv=None):
    """Run one seeded training series from the peers' private configuration."""
    parser = argparse.ArgumentParser(description="Offline Q-learning trainer.")
    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="RNG seed; echoed in the output so the run can be reproduced",
    )
    parser.add_argument("--config-root", default=_DEFAULT_CONFIG_ROOT)
    args = parser.parse_args(argv)

    config = load_config(os.path.join(args.config_root, _SHARED_CONFIG))
    cop_settings = load_strategy_settings(_COP_CONFIG_DIR, args.config_root)
    thief_settings = load_strategy_settings(_THIEF_CONFIG_DIR, args.config_root)

    scores = train_tournament(config, cop_settings, thief_settings, args.seed)
    _report(args.seed, config, cop_settings, thief_settings, scores)
    return scores


if __name__ == "__main__":
    main()
