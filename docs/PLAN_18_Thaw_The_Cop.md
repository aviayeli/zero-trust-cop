# PLAN 18 — The cop must not be frozen by a signal it cannot verify

Derived from `PRD_18_Thaw_The_Cop.md`.

## 1. A filter on the move set, not a new policy

The Q-tables stay exactly as trained (FR6). The change constrains WHICH moves
the existing policy may pick from, at the one moment the belief is provably
wrong. `manhattan_primary_action` already narrows to a distance-optimal set
and lets the table rank it; this narrows the set first.

```
decide(state) ->
    if role is cop and belief == our cell and we did not capture:
        the belief is FALSIFIED -> exclude STAY, prefer unvisited
    if consecutive STAY >= bound:
        exclude STAY                              (both roles, FR2)
    otherwise: unchanged
```

Everything else -- state key, table, tie-break, hints, deception -- is
untouched.

## 2. Why "arrived and did not capture" is a real refutation

This is the strongest signal available on a wire with no position: capture is
resolved by claim and honest answer, so a cop standing on the thief's cell
*would* have a capture to claim. Standing there with none is proof the thief
is elsewhere. It needs no model of their honesty and no new message.

Gemini ranked exactly this first for robustness, above physical-plausibility
filtering of their grid, because it is empirical rather than inferential.

## 3. Where the exclusion goes

`strategy.fallback._optimal_steps` computes the distance-optimal set. A
`forbid` parameter threading through `manhattan_primary_action` keeps the
change inside the one function that already decides what is choosable, rather
than post-filtering a chosen move -- post-filtering would pick a replacement
the distance rule never sanctioned.

`AgentPolicy.decide` owns the run counter, because it is the only object that
persists across a sub-game's steps and already holds role and pheromones.

## 4. Preferring unvisited over random (FR3)

A random walk re-treads. The cop keeps the cells it has occupied this
sub-game and, among the moves left after exclusion, prefers one leading to a
cell it has not stood on. That is a sweep, is deterministic and replayable,
and costs one set.

## 5. Configuration (FR5)

| key | in | meaning |
| --- | --- | --- |
| `max_consecutive_stay` | `config/<role>/game.toml` `[strategy]` | the FR2 bound |

Private per-role settings, not the shared contract: it changes no agreed term
and must not perturb the terms hash.

## 6. Modules

| module | change | budget |
| --- | --- | --- |
| `src/strategy/fallback.py` | `forbid` in `_optimal_steps` / `manhattan_primary_action` | 141 -> ~150 |
| `src/strategy/thaw.py` | the falsification rule and the STAY counter | new, <=150 |
| `src/agent/agent_core.py` | `decide` consults it | 92 -> ~105 |
| `src/strategy/settings.py` | load `max_consecutive_stay` | +2 |

## 7. Test plan (written first)

`tests/strategy/test_thaw.py`:

1. a cop whose belief equals its own cell does not choose STAY
2. …and prefers a cell it has not occupied this sub-game
3. a cop whose belief is elsewhere is completely unaffected
4. a THIEF standing on its believed cell may still STAY (FR4)
5. consecutive STAY is bounded for the cop
6. consecutive STAY is bounded for the thief too (FR2)
7. the counter resets when a real move is taken
8. the bound comes from config, absent from source (FR5)
9. the Q-table still ranks within the surviving set (FR6)

`tests/strategy/test_thaw_replay.py`:

10. **the regression that matters**: replaying g01's real belief trajectory
    with the patched rule produces no 16-turn frozen run.

## 8. Order of work

PRD -> PLAN -> TODO -> tests -> `fallback` -> `thaw` -> `agent_core` ->
settings -> figures -> suite green -> replay the graded board.
