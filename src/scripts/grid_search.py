"""Search the runtime hyperparameters for a cop that catches the bluffer.

PRD_19 measured 0% capture against profile C in BOTH arms. The thaw removed
the freeze and did not produce a capture, so the question this asks is whether
any point in the live parameter space does -- without retraining, which is the
deeper fix and a 10,000-episode commitment.

Three of the four knobs are BELIEF parameters, not policy ones:
``decay_per_step`` and ``emit_intensity`` shape how fast the pheromone field
forgets and how sharply it peaks, and together they set how many turns the
argmax lags the opponent. ``max_consecutive_stay`` is the thaw's bound. That
is the whole lever we have on a table trained against true positions.

The search reports honestly when nothing helps. A grid over a space with no
good point should say so rather than crown the least-bad cell as a champion.
"""

from __future__ import annotations

import json
from dataclasses import replace
from itertools import product

from engine.barriers import populated_board
from engine.config import load_config
from mcp_server.server import create_app
from scripts.benchmark_simulation import Tally, _one_game
from scripts.thief_profiles import PROFILES

CONTRACT = "config/game.json"
DECAY = (0.05, 0.10, 0.15, 0.20, 0.25)
INTENSITY = (0.5, 0.7, 0.9, 1.0)
STAY_BOUND = (2, 3, 4, 5)


def _score(config, board, policy, profile, games: int, seed: int) -> dict:
    tally = Tally()
    for index in range(games):
        _one_game(profile, config, board, policy, seed + index, True, tally)
    return tally.row()


def search(profile_name: str = "C_bluffer", games: int = 200,
           seed: int = 20260826, config_root=None) -> dict:
    """Every combination, scored on capture rate then on steps.

    Returns ``{"cells": [...], "champion": ...}``; ``champion`` is None when
    no cell captured anything, which is a result and not a failure to report.
    """
    base = load_config(CONTRACT)
    profile = PROFILES[profile_name]
    app = create_app("police", config_root=config_root)
    cells = []

    for decay, intensity, bound in product(DECAY, INTENSITY, STAY_BOUND):
        config = replace(base, pheromone_decay=decay,
                         pheromone_center_intensity=intensity)
        app.policy.settings = replace(app.policy.settings,
                                      max_consecutive_stay=bound)
        row = _score(config, populated_board(config), app.policy, profile,
                     games, seed)
        cells.append({"decay_per_step": decay, "emit_intensity": intensity,
                      "max_consecutive_stay": bound, **row})

    captured = [cell for cell in cells if cell["capture_rate"] > 0]
    champion = None
    if captured:
        champion = max(captured, key=lambda cell: (
            cell["capture_rate"], -(cell["mean_steps_to_capture"] or 1e9)))
    return {"profile": profile_name, "games_per_cell": games,
            "cells": cells, "champion": champion}


def main(argv=None) -> dict:
    import argparse

    parser = argparse.ArgumentParser(description="Grid-search the belief knobs.")
    parser.add_argument("--profile", default="C_bluffer", choices=tuple(PROFILES))
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    report = search(args.profile, args.games, args.seed)
    best = report["champion"]
    print(f"cells searched: {len(report['cells'])}")
    print(f"champion: {json.dumps(best) if best else 'NONE captured anything'}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    return report


if __name__ == "__main__":
    main()
