"""Measure the thawed cop under BELIEF, not under truth (PRD_19).

`tournament_loop.play_episode` hands `state_key` the opponent's real position,
so `hybrid_opponent_cell` returns it and never consults the pheromone field.
The freeze this benchmark exists to measure requires that fallback, so a run
through the existing harness would exercise none of the code under test and
report a clean bill for a bug it cannot reach.

This reproduces what the WIRE does instead: the thief emits a smell trail, we
read only its argmax into our field, and the cop decides from that. What the
thief transmits and where it actually is are separate -- which is the whole
exploit, and profile C is built on it.

Both arms are run on the same seeds (FR4). A capture rate with no baseline
beside it says nothing about the change that produced it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from random import Random

from engine.barriers import populated_board
from engine.config import load_config
from mcp_server.server import create_app
from mcp_server.smell_reader import strongest_cell
from mcp_server.smell_trail import SmellTrail
from scripts.thief_profiles import PROFILES, _legal
from strategy.thaw import Thaw

CONTRACT = "config/game.json"


@dataclass
class Tally:
    """What one profile's arm produced."""

    games: int = 0
    captures: int = 0
    steps_to_capture: list = field(default_factory=list)
    stays: int = 0
    longest_stay: int = 0
    thaw_fired: int = 0

    def row(self) -> dict:
        mean = (sum(self.steps_to_capture) / len(self.steps_to_capture)
                if self.steps_to_capture else None)
        return {
            "games": self.games,
            "capture_rate": round(100 * self.captures / self.games, 1)
            if self.games else 0.0,
            "mean_steps_to_capture": round(mean, 1) if mean else None,
            "stay_moves": self.stays,
            "longest_stay_run": self.longest_stay,
            "thaw_fired": self.thaw_fired,
        }


def _one_game(profile, config, board, policy, seed: int, thawed: bool,
              tally: Tally) -> None:
    """One episode: the thief evades and transmits, the cop believes and acts."""
    rng = Random(seed)
    size = config.grid_size
    cop, thief = tuple(config.cop_start), tuple(config.thief_start)
    trail = SmellTrail(config)
    policy.pheromones.__init__(config)          # a fresh belief per game
    thaw = Thaw("cop", policy.settings.max_consecutive_stay)
    run = 0

    for _ in range(config.max_moves):
        thief, faked = profile(board, thief, cop, rng, size)
        trail.step(faked or thief)              # what they TRANSMIT
        heard = strongest_cell(trail.grid())
        policy.pheromones.advance(deposits=[heard] if heard else [])

        belief = policy.pheromones.strongest()
        forbid = thaw.forbid(position=cop, belief=belief) if thawed else ()
        if forbid:
            tally.thaw_fired += 1
        move = policy.decide(policy.state_key(cop, None, board), rng, forbid)[0]
        thaw.took(move, position=cop)
        cop = _legal(board, cop, move)

        run = run + 1 if move == "STAY" else 0
        tally.stays += 1 if move == "STAY" else 0
        tally.longest_stay = max(tally.longest_stay, run)
        if cop == thief:
            tally.captures += 1
            tally.steps_to_capture.append(_ + 1)
            break
    tally.games += 1


def benchmark(games: int = 125, seed: int = 20260826,
              config_root=None) -> dict:
    """Every profile, both arms, same seeds. Returns a nested report."""
    config = load_config(CONTRACT)
    board = populated_board(config)
    policy = create_app("police", config_root=config_root).policy

    report: dict = {}
    for name, profile in PROFILES.items():
        report[name] = {}
        for arm, thawed in (("thawed", True), ("unthawed", False)):
            tally = Tally()
            for index in range(games):
                _one_game(profile, config, board, policy, seed + index,
                          thawed, tally)
            report[name][arm] = tally.row()
    return report


def main(argv=None) -> dict:
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark the thawed cop.")
    parser.add_argument("--games", type=int, default=125,
                        help="games per profile per arm; 125 x 4 x 2 = 1000")
    parser.add_argument("--seed", type=int, default=20260826)
    parser.add_argument("--out", default=None, help="write the report as JSON")
    args = parser.parse_args(argv)

    report = benchmark(args.games, args.seed)
    print(json.dumps(report, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    return report


if __name__ == "__main__":
    main()
