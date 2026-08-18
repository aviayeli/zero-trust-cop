"""Episode-level machinery for the off-manifold probe (`benchmark_offmanifold`).

Kept separate from the published run so the mechanics — how a start pair is
drawn, how one greedy episode is played, how a cell is aggregated — can be
tested without loading the shipped tables or the benchmark's own config.

`flat_state_rate` counts the decisions the fallback governs, and asks
`strategy.fallback.tiebreak_action` itself rather than re-deriving flatness
here: the probe must measure the shipped rule, not a copy of it.
"""

import random
from dataclasses import replace

from engine.barriers import barrier_layout
from engine.game_loop import GameEpisode
from strategy.fallback import tiebreak_action
from strategy.qvalues import QValues


def start_pairs(config, count: int, seed: int) -> list:
    """Draw `count` distinct FREE (cop, thief) start cells from `seed`.

    Barrier cells are excluded: an agent placed inside a wall is not a start
    the engine could ever produce, and every move out of it would resolve to
    STAY (PLAN.md §4.3).
    """
    rng = random.Random(seed)
    blocked = barrier_layout(config)
    cells = [
        (row, col)
        for row in range(config.grid_size)
        for col in range(config.grid_size)
        if (row, col) not in blocked
    ]
    pairs = []
    while len(pairs) < count:
        cop, thief = rng.choice(cells), rng.choice(cells)
        if cop != thief:
            pairs.append((cop, thief))
    return pairs


def build_table(config, settings, role, table_path=None) -> QValues:
    """Build a match-mode table; `table_path` of None leaves it empty.

    An empty table is the pure greedy-Manhattan heuristic: every state it
    meets is flat, so every decision falls to the distance tie-break.
    """
    greedy = replace(settings, exploration_rate=settings.match_exploration_rate)
    values = QValues(config, greedy, role=role)
    if table_path is not None:
        values.load(table_path)
    return values


def _evader_move(thief, episode, config, rng) -> str:
    """One evader move; a uniform draw when no table backs the opponent."""
    if thief is None:
        return rng.choice(config.move_set)
    state = thief.state_key(
        episode.thief_state.position, episode.cop_state.position,
        barrier_layout(config),
    )
    return thief.best_action(state)


def play(config, cop, thief, cop_start, thief_start, seed) -> tuple:
    """Play one greedy episode; return (captured, turns, decisions, flat)."""
    episode = GameEpisode(config)
    episode.reset()
    blocked = barrier_layout(config)
    episode.cop_state.position = cop_start
    episode.thief_state.position = thief_start
    rng = random.Random(seed)
    decisions = flat = 0
    result = None
    while not episode.is_terminated:
        state = cop.state_key(
            episode.cop_state.position, episode.thief_state.position, blocked
        )
        decisions += 1
        if tiebreak_action(state, config.move_set, "cop", cop.q_value) is not None:
            flat += 1
        move = cop.best_action(state)
        result = episode.step(move, _evader_move(thief, episode, config, rng))
    return result.captured, episode.turn_count, decisions, flat


def evaluate(config, cop, thief, pairs, seed) -> dict:
    """Aggregate one (cop policy, opponent) cell of the published table.

    `mean_turns` is None rather than 0.0 when nothing was ever captured: a
    policy that never wins has no turns-to-capture, and averaging it to zero
    would read as the fastest pursuit in the table.
    """
    captures, turns, decisions, flat = 0, [], 0, 0
    for offset, (cop_start, thief_start) in enumerate(pairs):
        captured, played, seen, unlearned = play(
            config, cop, thief, cop_start, thief_start, seed + offset
        )
        decisions += seen
        flat += unlearned
        if captured:
            captures += 1
            turns.append(played)
    return {
        "capture_rate": 100.0 * captures / len(pairs),
        "mean_turns": sum(turns) / len(turns) if turns else None,
        "flat_state_rate": 100.0 * flat / decisions,
    }
