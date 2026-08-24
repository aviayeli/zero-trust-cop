"""The published off-manifold run: what the shipped tables do from unseen starts.

`docs/PLAN.md` §10.10 quotes this script's output, and
`tests/scripts/test_benchmark_plan_claims.py` re-derives that table from a real
run — the numbers in the document are checked, not remembered.

Self-play converges onto one trajectory manifold, so a series capture rate says
nothing about the states off it. Here both peers are in-process and greedy
(`match_exploration_rate`), the grid is bare, and every start pair is drawn
from a seeded RNG, so a run is reproducible from `config/benchmark.json` alone
— sample size, seed and opponent set all live there, none of them in source.

Three cop policies are compared: the trained table read WITHOUT a role (the
pre-fallback "always N" behaviour), the same table WITH one, and a cop carrying
no table at all, which is the pure greedy-Manhattan heuristic.
"""

import argparse
import json
import os
from dataclasses import replace

from dataclasses import replace

from engine.config import load_config
from scripts.offmanifold_probe import build_table, evaluate, start_pairs
from strategy.fallback import MANHATTAN_PRIMARY, QTABLE_PRIMARY
from strategy.settings import load_strategy_settings

_DEFAULT_CONFIG_ROOT = "config"
_SHARED_CONFIG = "game.json"
_BENCHMARK_CONFIG = "benchmark.json"
_COLUMNS = ("policy", "opponent", "capture_rate", "mean_turns", "flat_state_rate")


def load_benchmark_settings(config_root: str = _DEFAULT_CONFIG_ROOT) -> dict:
    """Read the probe's own tunables; none of them are inlined in Python."""
    path = os.path.join(config_root, _BENCHMARK_CONFIG)
    with open(path, "r", encoding="utf-8") as settings:
        return json.load(settings)


_BENCHMARK_BARRIER_SEED = 20260818


def benchmark(config_root: str = _DEFAULT_CONFIG_ROOT, seed=None, count=None) -> list:
    """Return one structured row per (cop policy, opponent) pair.

    `seed` and `count` of None take the published values from config, so the
    default call is exactly the run docs/PLAN.md §10.10 reports.
    """
    settings = load_benchmark_settings(config_root)
    seed = settings["seed"] if seed is None else seed
    count = settings["start_pairs"] if count is None else count
    config = replace(
        load_config(os.path.join(config_root, _SHARED_CONFIG)),
        # The board these published figures were measured on.
        # `barrier_seed` left the shipped contract when we agreed a
        # bare board with rstabcde; a benchmark that moved with a
        # negotiated value would be measuring the contract, not the
        # policy -- and on a bare board the evader survives 100%
        # whether its table is trained or empty.
        barrier_seed=_BENCHMARK_BARRIER_SEED,
    )
    police = load_strategy_settings("police", config_root)
    burglar = load_strategy_settings("thief", config_root)
    pairs = start_pairs(config, count, seed)

    table = police.qtable_path
    as_mode = {mode: replace(police, policy_mode=mode)
               for mode in (QTABLE_PRIMARY, MANHATTAN_PRIMARY)}
    cops = (
        # No role: the distance rule never runs. The original policy.
        ("qtable-only", build_table(config, as_mode[QTABLE_PRIMARY], None, table)),
        # Distance consulted only where the table is flat. Previously shipped.
        ("qtable-primary", build_table(config, as_mode[QTABLE_PRIMARY], "cop", table)),
        # Distance decides, the table breaks ties. Shipped now.
        ("manhattan-primary", build_table(config, as_mode[MANHATTAN_PRIMARY], "cop", table)),
        # Same distance rule, EMPTY table, so ties fall to move-set order.
        ("heuristic", build_table(config, as_mode[MANHATTAN_PRIMARY], "cop")),
    )
    # The opponent must be the evader that actually PLAYS, not the one that
    # trains: the two priorities are separate settings (peer_policy.py).
    evader = replace(burglar, policy_mode=burglar.match_policy_mode)
    thieves = {
        "random": None,
        "greedy": build_table(config, evader, "thief"),
        "trained": build_table(config, evader, "thief", evader.qtable_path),
    }
    return [
        dict(policy=policy, opponent=opponent,
             **evaluate(config, cop, thieves[opponent], pairs, seed))
        for policy, cop in cops
        for opponent in settings["opponents"]
    ]


def format_rows(rows: list) -> str:
    """Render the rows as a markdown table, `None` turns shown as `n/a`."""
    lines = ["| " + " | ".join(_COLUMNS) + " |", "|" + " :--- |" * len(_COLUMNS)]
    for row in rows:
        turns = "n/a" if row["mean_turns"] is None else f"{row['mean_turns']:.2f}"
        lines.append(
            f"| {row['policy']} | {row['opponent']} | {row['capture_rate']:.1f}% "
            f"| {turns} | {row['flat_state_rate']:.1f}% |"
        )
    return "\n".join(lines)


def main(argv=None) -> list:
    """Print the probe table; every tunable comes from config or the CLI."""
    parser = argparse.ArgumentParser(description="Off-manifold policy probe.")
    parser.add_argument("--seed", type=int, help="override config/benchmark.json")
    parser.add_argument("--start-pairs", type=int, help="override the sample size")
    parser.add_argument("--config-root", default=_DEFAULT_CONFIG_ROOT)
    args = parser.parse_args(argv)

    rows = benchmark(args.config_root, args.seed, args.start_pairs)
    print(format_rows(rows))
    return rows


if __name__ == "__main__":
    main()
