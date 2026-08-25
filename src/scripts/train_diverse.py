"""Offline training against a POOL of opponents rather than one mirror.

Self-play converged both tables onto each other's habits: measured against a
heuristic pursuer the shipped evader survived 2.2% where an EMPTY table
survived 69.8% (PLAN.md §10.10). Learning was a liability against anything it
had not trained against.

Each episode here draws its opponent from ``config/training.json`` — a
scripted greedy player, the co-evolving learner, or a random mover — and
draws a fresh BARRIER LAYOUT, so neither table can specialise to one
adversary or one board. Only the learner's table is updated: the scripted
sides are ``frozen`` (``strategy/opponents.py``).

The episode itself is unchanged. ``tournament_loop.play_episode`` already
implements the TD update and the shaping terms, and reusing it is what keeps
one definition of a training episode in the project.
"""

import argparse
import random
from dataclasses import replace

from engine.config import load_config
from engine.game_loop import GameEpisode
from scripts.opponent_pool import load_training_settings, pick_bucket
from scripts.run_tournament import build_policy
from scripts.tournament_loop import play_episode
from strategy.opponents import build_pool, fresh_opponent, frozen
from strategy.settings import load_strategy_settings

_SHARED = "config/game.json"
_ROLE_DIR = {"cop": "police", "thief": "thief"}


def layout_seed_for(episode: int, settings) -> int:
    """The barrier layout this episode trains on.

    Cycling a fixed pool rather than drawing freshly keeps a run reproducible
    from its seed while still denying either table a single board to memorise.
    """
    return episode % settings.layout_seeds


def _opponent(bucket, learner, pool, config, engine_role):
    """The opposing policy for one episode, frozen unless it is the learner."""
    if bucket == "learning":
        return learner
    return frozen(fresh_opponent(pool[(bucket, engine_role)], config))


def train_diverse(config, seed, episodes, cop_path, thief_path, config_root=None):
    """Train both tables against the configured pool; return a run summary."""
    settings = load_training_settings(config_root)
    master = random.Random(seed)
    rng_cop = random.Random(master.random())
    rng_thief = random.Random(master.random())
    chooser = random.Random(master.random())

    cop = build_policy("cop", config, _match(config_root, "cop"))
    thief = build_policy("thief", config, _match(config_root, "thief"))
    faced = dict.fromkeys(settings.opponent_mix, 0)
    pool = build_pool(config, config_root)

    for episode in range(episodes):
        board = replace(config, barrier_seed=layout_seed_for(episode, settings))
        bucket = pick_bucket(settings.opponent_mix, chooser.random())
        faced[bucket] += 1
        # The cop is always the learner; the THIEF side is drawn from the pool
        # on even episodes and the roles swap on odd ones, so both tables meet
        # the full mix rather than one of them always facing the learner.
        if episode % 2:
            learners = (cop, _opponent(bucket, thief, pool, board, "thief"))
        else:
            learners = (_opponent(bucket, cop, pool, board, "cop"), thief)
        play_episode(GameEpisode(board), *learners, rng_cop, rng_thief)
        cop.qvalues.decay_epsilon()
        thief.qvalues.decay_epsilon()

    cop.qvalues.save(cop_path)
    thief.qvalues.save(thief_path)
    return {
        "cop_entries": len(cop.qvalues.q_table),
        "thief_entries": len(thief.qvalues.q_table),
        "opponents": faced,
    }


def _match(config_root, engine_role):
    """Training settings for one role, straight from its private workspace."""
    return load_strategy_settings(_ROLE_DIR[engine_role], config_root)


def main(argv=None):
    """Run one seeded diverse-opponent series from configuration."""
    parser = argparse.ArgumentParser(description="Diverse-opponent trainer.")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--episodes", type=int, default=None)
    parser.add_argument("--config-root", default=None)
    args = parser.parse_args(argv)

    config = load_config(_SHARED)
    settings = load_training_settings(args.config_root)
    episodes = settings.episodes if args.episodes is None else args.episodes
    summary = train_diverse(
        config, args.seed, episodes,
        load_strategy_settings("police", args.config_root).qtable_path,
        load_strategy_settings("thief", args.config_root).qtable_path,
        args.config_root,
    )
    print(f"seed={args.seed}")
    print(f"episodes={episodes}")
    for bucket, count in summary["opponents"].items():
        print(f"faced_{bucket}={count}")
    print(f"cop_entries={summary['cop_entries']}")
    print(f"thief_entries={summary['thief_entries']}")
    return summary


if __name__ == "__main__":
    main()
