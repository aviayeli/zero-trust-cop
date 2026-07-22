# PLAN — Phase 1: Base Logic

Derived from `docs/PRD_01_Base_Logic.md`. Defines the software architecture only. No code and no `TODO.md` yet — awaiting approval.

## Design Principles Applied

- **Simplicity First / Surgical Changes**: each module owns exactly one concern; nothing is built for phases 2+ (no networking, no MCP, no scoring/pheromones).
- **150-line limit**: modules are split along the natural seams in the PRD (grid, agents, resolution, config, errors) so each stays well under 150 lines. If any module approaches the limit during implementation, it must be split further before it is exceeded — not after.
- **No hardcoded hyperparameters**: exactly one module (`config.py`) is allowed to know the path to `config/game.json`; every other module receives values through it, never as literals.
- **Strict TDD**: this PLAN's job is to define module boundaries and public interfaces precisely enough that `TODO.md` can sequence failing tests before any implementation.

## FR5 Turn-Resolution & Tie-Break Rule (locked)

This is the authoritative resolution algorithm every module below must implement identically to `PRD_01_Base_Logic.md` FR5:

1. **Simultaneous evaluation** — compute both agents' *intended* new positions from the current board state, before committing either.
2. **Barrier & bounds check** — for each agent independently: if its intended position is off-grid or on a barrier cell, that agent's move resolves to `STAY` (i.e. its position does not change). This check is per-agent and does not depend on the other agent's move.
3. **Capture check** — after both positions are resolved:
   - a) `new_cop_pos == new_thief_pos` → capture, or
   - b) `new_cop_pos == old_thief_pos AND new_thief_pos == old_cop_pos` → capture (agents swapped cells / crossed paths).
4. Only a malformed action token (not one of `N/S/E/W/STAY`) is rejected as illegal input, prior to step 1 — it never reaches resolution.

## Module Architecture

```
zero-trust-cop/
├── CLAUDE.md
├── config/
│   └── game.json
├── docs/
│   ├── PRD_01_Base_Logic.md
│   ├── PLAN.md
│   └── TODO.md              (next step, not yet created)
├── src/
│   └── engine/
│       ├── __init__.py
│       ├── config.py         # loads & validates config/game.json
│       ├── actions.py        # Action enum/type + validity check
│       ├── board.py          # grid bounds + barrier placement/lookup
│       ├── player.py         # agent position state + intended-move computation
│       ├── resolver.py       # FR5 algorithm: bounds/barrier resolution + capture check
│       ├── game_loop.py       # episode orchestration: init, step, termination (FR6), history
│       └── errors.py         # exception types (e.g. InvalidActionError, BarrierLimitError)
└── tests/
    └── engine/
        ├── test_config.py
        ├── test_actions.py
        ├── test_board.py
        ├── test_player.py
        ├── test_resolver.py
        └── test_game_loop.py
```

## Module Responsibilities & Interfaces

### `config.py`
- **Owns**: reading and parsing `config/game.json`; the single source of truth for every hyperparameter (`grid_size`, `cop_start`, `thief_start`, `move_set`, `max_barriers`, `max_moves`, `survival_threshold`).
- **Exposes**: a `GameConfig` (dataclass or similar) with typed fields for the above, and a `load_config(path: str) -> GameConfig` function.
- **Depends on**: nothing (leaf module).
- **Used by**: every other module — no module reads `config/game.json` directly except this one.

### `actions.py`
- **Owns**: the fixed action vocabulary and the "is this a legal token" check described in FR3/step 4 above.
- **Exposes**: an `Action` enum (`N, S, E, W, STAY`) and `parse_action(token: str) -> Action`, raising `InvalidActionError` (from `errors.py`) for anything outside the set. Also exposes the `(row, col)` delta for each directional action.
- **Depends on**: `errors.py`.
- **Used by**: `player.py`, `resolver.py`, `game_loop.py`.

### `board.py`
- **Owns**: grid bounds (from `GameConfig.grid_size`) and barrier state (placement, lookup, count).
- **Exposes**: `Board` class with `in_bounds(pos) -> bool`, `is_barrier(pos) -> bool`, `place_barrier(pos)` (enforces the 14-barrier cap and occupancy rule from FR4, raising `BarrierLimitError`/`IllegalBarrierError` as appropriate), and `barrier_count`.
- **Depends on**: `config.py`, `errors.py`.
- **Used by**: `resolver.py`, `game_loop.py`.

### `player.py`
- **Owns**: a single agent's position state and the pure computation of an *intended* next position given a current position and an `Action` (no bounds/barrier awareness — that's the resolver's job, per FR5 step 2's separation of concerns).
- **Exposes**: `PlayerState` (position, role) and `intended_position(state, action) -> (row, col)`.
- **Depends on**: `actions.py`.
- **Used by**: `resolver.py`, `game_loop.py`.

### `resolver.py`
- **Owns**: the FR5 algorithm exactly as locked above — steps 1–3 (simultaneous evaluation, per-agent barrier/bounds resolution to `STAY`, capture check). This is the only module that implements the tie-break/capture rule; nothing else duplicates it.
- **Exposes**: `resolve_turn(board, cop_state, thief_state, cop_action, thief_action) -> TurnResult`, where `TurnResult` carries the two resolved positions and a `captured: bool` flag.
- **Depends on**: `board.py`, `player.py`, `actions.py`.
- **Used by**: `game_loop.py`.

### `game_loop.py`
- **Owns**: episode-level orchestration — initializing Cop/Thief at their configured start positions, driving one `step()` per turn via `resolver.py`, tracking turn count, enforcing FR6 termination (capture from `TurnResult.captured`, or turn count reaching `max_moves`), and recording full episode history for deterministic replay (FR7).
- **Exposes**: `GameEpisode` class with `reset()`, `step(cop_action, thief_action) -> TurnResult`, `is_terminated -> bool`, `history` (ordered list of resolved turns), and a `replay(actions: list[tuple]) -> GameEpisode` helper that reconstructs an episode deterministically from a recorded action sequence.
- **Depends on**: `config.py`, `board.py`, `player.py`, `resolver.py`, `errors.py`.
- **Used by**: test suite and, in later phases, the networking/MCP layer (out of scope here).

### `errors.py`
- **Owns**: all engine-specific exception types (`InvalidActionError`, `BarrierLimitError`, `IllegalBarrierPlacementError`, etc.) so every module raises from a shared, importable set rather than ad hoc exceptions.
- **Depends on**: nothing (leaf module).

## Data Flow (per turn)

```
game_loop.step(cop_action_token, thief_action_token)
  → actions.parse_action() on each token           [rejects malformed tokens]
  → resolver.resolve_turn(board, cop_state, thief_state, cop_action, thief_action)
      → player.intended_position() for each agent
      → board.in_bounds() / board.is_barrier() per agent → resolve to STAY if blocked
      → capture check (same-cell OR swap)
      → return TurnResult
  → game_loop commits new positions, appends to history, increments turn count
  → game_loop checks termination (captured OR turn_count == max_moves)
```

## Determinism Strategy (FR7)

- No module uses randomness, wall-clock time, or any other non-deterministic source.
- `GameEpisode.history` records every `(cop_action, thief_action, TurnResult)` in order, which is sufficient to fully reconstruct an episode via `replay()`.
- All state mutation happens only inside `game_loop.py`'s `step()`; `resolver.py` and `player.py` are pure functions over their inputs, which makes determinism straightforward to test (same inputs → same outputs, no hidden state).

## Test Strategy (per TDD, detail belongs in TODO.md)

Each module above gets a corresponding `tests/engine/test_*.py` written and failing *before* that module's implementation exists, per `CLAUDE.md`. At minimum, `test_resolver.py` must cover:
- Both agents make unobstructed legal moves.
- One agent's move is blocked by bounds → resolves to `STAY`; other agent's move is unaffected.
- One agent's move is blocked by a barrier → resolves to `STAY`.
- Both agents move into the same cell → capture (case a).
- Agents swap cells → capture (case b).
- A near-miss (agents pass through adjacent cells without swapping or colliding) → no capture.

## Open Items for TODO.md

- Exact ordering/granularity of TDD tasks per module.
- Whether `errors.py` and `actions.py` are built first (both are leaf/near-leaf dependencies everything else needs).
- Fixture/config strategy for tests (e.g. a test-only `config/game.json` fixture vs. loading the real one).

## Approval Gate

Per the document lifecycle in `CLAUDE.md`, no implementation code and no `TODO.md` task list is written until this architecture is approved.
