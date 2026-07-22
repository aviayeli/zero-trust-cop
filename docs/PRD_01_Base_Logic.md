# PRD 01 — Base Logic (Phase 1)

## Status
Draft — Phase 1 only. No networking, no FastMCP, no LLM agents. Local, in-process game engine only.

## Objective
Implement a deterministic, local Dec-POMDP (decentralized partially-observable Markov decision process) game engine simulating a Cop pursuing a Thief on a grid, matching the parameters in `config/game.json`. This engine is the foundation all later phases (networking, agent integration, league play) build on — it must be correct and fully tested before any later phase begins.

## Scope
In scope:
- Grid representation and coordinate system.
- Cop and Thief agent state (position, history).
- Turn/step resolution for simultaneous moves.
- Barrier placement and enforcement.
- Move legality checks (grid bounds, barriers).
- Episode termination conditions (capture, max moves reached).
- Deterministic replay: identical inputs (starting state + action sequence) always produce identical outputs.

Out of scope (future phases):
- Networking / message passing between agents.
- FastMCP server or tool exposure.
- LLM-driven agent decision-making.
- Pheromone system, scoring/league logic, rate limiting.
- Any UI or visualization.

## Source of Truth
All parameters below are read from `config/game.json` at runtime — none may be hardcoded in implementation code, per `CLAUDE.md`.

## Functional Requirements

### FR1 — Grid
- The board is a **7×7** grid (`grid_size: 7`).
- Axis origin is the top-left corner, 0-indexed (`axis_origin_corner: topleft`, `axis_start_index: 0`). Valid coordinates are `(row, col)` with `row, col ∈ [0, 6]`.

### FR2 — Agent Start Positions
- **Cop** starts at position `[0, 0]` (`cop_start`).
- **Thief** starts at position `[3, 3]` (`thief_start`).
- Both positions must be reset to these exact values at the start of every episode.

### FR3 — Action Space
- Exactly **5 allowed actions** per agent per turn: `N`, `S`, `E`, `W`, `STAY` (`move_set`).
- `N`/`S`/`E`/`W` move the agent one cell in that direction; `STAY` leaves the agent's position unchanged.
- A submitted action token not in `{N, S, E, W, STAY}` is **illegal** and must be rejected deterministically before resolution (invalid input, not a normal turn).
- A syntactically valid action (`N/S/E/W`) that would move the agent outside the grid bounds (FR1) or into a barrier (FR4) is **not** rejected — per FR5, it is resolved to `STAY` for that agent during turn resolution, and the turn proceeds normally.

### FR4 — Barriers
- The Cop may place up to **14 barriers** total across an episode (`max_barriers`).
- A barrier occupies a single grid cell and blocks any agent from moving into or through that cell.
- Barriers may not be placed on a cell currently occupied by the Cop or Thief, nor on a cell that would make the Thief's start or the Cop's own position unreachable in a way that immediately ends the episode by soft-lock (trapping is a valid strategic outcome only if it is a legal, intentional sequence of legal placements — the engine does not need to solve reachability, only enforce the occupancy rule).
- Barrier count is tracked and enforced; a 15th placement attempt is illegal and rejected.

### FR5 — Turn Resolution
- Each turn, both Cop and Thief submit one action simultaneously (this is a Dec-POMDP: neither agent's action for the current turn depends on seeing the other's current-turn action). Resolution proceeds in this fixed order:
  1. **Simultaneous evaluation**: both agents' intended moves are computed against the current board state before either position is committed.
  2. **Barrier & bounds check**: if an agent's intended move would leave the grid or land on a barrier cell, that agent's move resolves to `STAY` instead. This is independent per agent — one agent resolving to `STAY` does not affect the other's intended move.
  3. **Capture check**: after both new positions are resolved, a capture occurs if either:
     - a) `new_cop_pos == new_thief_pos` (both land on the same cell), or
     - b) `new_cop_pos == old_thief_pos AND new_thief_pos == old_cop_pos` (the agents swap cells / cross paths).
- Turn count increments once per resolved turn.

### FR6 — Termination Conditions
- **Capture**: episode ends immediately when FR5's capture check (a or b) is satisfied.
- **Max moves**: episode ends when turn count reaches **35** (`max_moves`), if no capture has occurred (`survival_threshold: 35` — Thief survives).
- No other termination conditions exist in Phase 1 (scoring, technical loss, etc. are out of scope here).

### FR7 — Determinism
- Given an identical starting state and an identical, ordered sequence of (Cop action, Thief action) pairs, the engine must produce byte-identical resulting states on every run.
- No use of unseeded randomness, wall-clock time, or any other non-deterministic source anywhere in the base logic.
- The engine must support full episode replay from a recorded action sequence.

## Non-Functional Requirements
- Every module obeys the 150-line-per-file limit in `CLAUDE.md`; split by responsibility (e.g. grid, agent state, turn resolver, barrier manager) rather than exceeding it.
- All hyperparameters (`grid_size`, `cop_start`, `thief_start`, `move_set`, `max_barriers`, `max_moves`, `survival_threshold`) are loaded from `config/game.json`; none are literals in source.
- Strict TDD: every FR above must have a corresponding failing test written before its implementation.

## Acceptance Criteria
- [ ] A fresh episode initializes Cop at `[0,0]` and Thief at `[3,3]` on a 7×7 grid, read from config.
- [ ] Only `N/S/E/W/STAY` are accepted as actions; any other input is rejected.
- [ ] An invalid action token (not `N/S/E/W/STAY`) is rejected without mutating state; a valid action that would go out of bounds or into a barrier resolves to `STAY` instead of erroring.
- [ ] A same-cell capture and a cell-swap ("crossing paths") capture are both detected and terminate the episode.
- [ ] Barrier placement is capped at 14 and enforced.
- [ ] An episode terminates on capture (same cell) or at 35 moves, and not otherwise.
- [ ] Replaying the same action sequence against the same initial state twice yields identical episode histories.
- [ ] No file in the implementation exceeds 150 lines.
- [ ] No hyperparameter is hardcoded; all trace to `config/game.json`.

## Next Steps (Document Lifecycle)
Per `CLAUDE.md`, implementation may not begin until `docs/PLAN.md` is written from this PRD and approved, and no task is executed until it is broken out in `docs/TODO.md`.
