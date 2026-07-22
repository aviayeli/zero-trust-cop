# TODO — Phase 1: Base Logic

Derived from `docs/PLAN.md` (approved) and `docs/PRD_01_Base_Logic.md`. Executes strict TDD per `CLAUDE.md`: for every module, its test file is written and confirmed **failing** immediately before its implementation file is written, and confirmed **passing** immediately after. No task here writes implementation code before its paired test task.

Order follows `PLAN.md`'s dependency chain: `errors.py` → `config.py` → `actions.py` → `board.py` → `player.py` → `resolver.py` → `game_loop.py`, then cross-module integration/replay tests.

## 0. Scaffolding (no game logic yet)

- [x] Create `src/engine/__init__.py` (empty package marker).
- [x] Create `tests/engine/__init__.py` (empty package marker). *(Later removed in Task 1: a `tests/engine` package collides with the `src/engine` package name under pytest import; resolved via `--import-mode=importlib` + no `__init__.py` in `tests/`.)*
- [x] Add/confirm a test runner config (e.g. `pytest.ini` / `pyproject.toml` `[tool.pytest]` section) so `tests/engine/` is discoverable.
- [x] Confirm the test runner executes with zero collected tests and no errors (sanity check before any test content exists).

## 1. `errors.py` (leaf — no dependencies)

- [x] **Test first**: write `tests/engine/test_errors.py` asserting:
  - [x] `InvalidActionError` exists and is an `Exception` subclass.
  - [x] `BarrierLimitError` exists and is an `Exception` subclass.
  - [x] `IllegalBarrierPlacementError` exists and is an `Exception` subclass.
  - [x] Each error type can be raised and caught with a custom message.
- [x] Run tests and confirm they **fail** (module does not exist yet).
- [x] **Implement** `src/engine/errors.py` with exactly the exception classes required to pass the above — nothing else.
- [x] Run tests and confirm they **pass** (6 passed).
- [x] Confirm `errors.py` is under 150 lines (19 lines).

## 2. `config.py` (leaf — no dependencies)

- [x] **Test first**: write `tests/engine/test_config.py` asserting:
  - [x] `load_config(path)` loads `config/game.json` and returns a `GameConfig` with `grid_size == 7`.
  - [x] `GameConfig.cop_start == [0, 0]`.
  - [x] `GameConfig.thief_start == [3, 3]`.
  - [x] `GameConfig.move_set == ["N", "S", "E", "W", "STAY"]`.
  - [x] `GameConfig.max_barriers == 14`.
  - [x] `GameConfig.max_moves == 35`.
  - [x] `GameConfig.survival_threshold == 35`.
  - [x] `load_config` raises a clear error (not a silent default) if the file is missing or a required key is absent.
- [x] Run tests and confirm they **fail** (module does not exist yet).
- [x] **Implement** `src/engine/config.py` — `GameConfig` dataclass + `load_config()` — reading only from `config/game.json`, with no hyperparameter values duplicated as literals elsewhere in the module.
- [x] Run tests and confirm they **pass** (3 passed; grep confirms no literal game values in config.py).
- [x] Confirm `config.py` is under 150 lines (44 lines).

## 3. `actions.py` (depends on: `errors.py`)

- [ ] **Test first**: write `tests/engine/test_actions.py` asserting:
  - [ ] `Action` enum has exactly the 5 members `N, S, E, W, STAY` (and no others).
  - [ ] `parse_action("N")` through `parse_action("STAY")` each return the correct `Action` member.
  - [ ] `parse_action("n")` / lowercase or any token outside `{N,S,E,W,STAY}` raises `InvalidActionError`.
  - [ ] Each directional `Action` maps to the correct `(row, col)` delta (e.g. `N → (-1, 0)`, `S → (1, 0)`, `E → (0, 1)`, `W → (0, -1)`); `STAY → (0, 0)`.
- [ ] Run tests and confirm they **fail**.
- [ ] **Implement** `src/engine/actions.py` — `Action` enum, `parse_action()`, and the delta lookup — sourcing the valid token set from `GameConfig.move_set` rather than a hardcoded literal list.
- [ ] Run tests and confirm they **pass**.
- [ ] Confirm `actions.py` is under 150 lines.

## 4. `board.py` (depends on: `config.py`, `errors.py`)

- [ ] **Test first**: write `tests/engine/test_board.py` asserting:
  - [ ] `Board.in_bounds((r, c))` is `True` for all `r, c ∈ [0, 6]` and `False` for any coordinate outside that range, on a `grid_size == 7` board.
  - [ ] `Board.is_barrier(pos)` is `False` before any placement.
  - [ ] `place_barrier(pos)` makes `is_barrier(pos)` become `True`.
  - [ ] `place_barrier` on a cell currently occupied by the Cop or Thief raises `IllegalBarrierPlacementError`.
  - [ ] Placing a 15th barrier raises `BarrierLimitError`; `barrier_count` stops incrementing after the cap.
  - [ ] `barrier_count` accurately reflects the number of successful placements at each step.
- [ ] Run tests and confirm they **fail**.
- [ ] **Implement** `src/engine/board.py` — `Board` class backed by `GameConfig.grid_size` and `GameConfig.max_barriers` — no hardcoded `7` or `14`.
- [ ] Run tests and confirm they **pass**.
- [ ] Confirm `board.py` is under 150 lines.

## 5. `player.py` (depends on: `actions.py`)

- [ ] **Test first**: write `tests/engine/test_player.py` asserting:
  - [ ] `PlayerState` holds a `position` and a `role` (cop/thief) and initializes to the position given.
  - [ ] `intended_position(state, Action.N)` returns `position + (-1, 0)` with no bounds/barrier awareness (i.e. it can return an out-of-grid coordinate — that check is explicitly not this module's job).
  - [ ] `intended_position(state, Action.STAY)` returns `position` unchanged.
  - [ ] `intended_position` is a pure function: calling it does not mutate `state.position`.
- [ ] Run tests and confirm they **fail**.
- [ ] **Implement** `src/engine/player.py` — `PlayerState` + `intended_position()`.
- [ ] Run tests and confirm they **pass**.
- [ ] Confirm `player.py` is under 150 lines.

## 6. `resolver.py` (depends on: `board.py`, `player.py`, `actions.py`) — implements the locked FR5 algorithm

- [ ] **Test first**: write `tests/engine/test_resolver.py` asserting, per the FR5 tie-break rule in `PLAN.md`:
  - [ ] Both agents make unobstructed legal moves → both positions update as intended, `captured == False`.
  - [ ] Cop's intended move is out of bounds → Cop resolves to `STAY`; Thief's unobstructed move is unaffected.
  - [ ] Thief's intended move lands on a barrier → Thief resolves to `STAY`; Cop's unobstructed move is unaffected.
  - [ ] Both agents' intended moves are simultaneously blocked (bounds and/or barrier) → both resolve to `STAY` independently, `captured` evaluated on the resolved (unchanged) positions.
  - [ ] Both agents move into the same cell → `TurnResult.captured == True` (case a, same-cell).
  - [ ] Agents swap cells (`new_cop_pos == old_thief_pos AND new_thief_pos == old_cop_pos`) → `TurnResult.captured == True` (case b, crossing paths).
  - [ ] Agents pass through adjacent cells without colliding or swapping → `captured == False`.
  - [ ] A capture case where one agent's move first resolves to `STAY` due to bounds/barrier, then that `STAY` position happens to equal the other agent's new position → capture still correctly detected on the *resolved* positions, not the originally intended ones.
- [ ] Run tests and confirm they **fail**.
- [ ] **Implement** `src/engine/resolver.py` — `TurnResult` + `resolve_turn()` implementing steps 1–3 of the FR5 algorithm from `PLAN.md` exactly, and only here.
- [ ] Run tests and confirm they **pass**.
- [ ] Confirm `resolver.py` is under 150 lines.

## 7. `game_loop.py` (depends on: `config.py`, `board.py`, `player.py`, `resolver.py`, `errors.py`)

- [ ] **Test first**: write `tests/engine/test_game_loop.py` asserting:
  - [ ] `GameEpisode.reset()` places Cop at `GameConfig.cop_start` and Thief at `GameConfig.thief_start`, turn count `0`, `is_terminated == False`.
  - [ ] `step(cop_token, thief_token)` with malformed tokens raises `InvalidActionError` and does not mutate state (turn count unchanged).
  - [ ] `step()` with two valid tokens advances turn count by exactly 1 and appends one entry to `history`.
  - [ ] `step()` returns the same `TurnResult` shape/values `resolver.resolve_turn()` would produce for the same inputs (no divergent logic re-implemented in `game_loop.py`).
  - [ ] Episode sets `is_terminated == True` immediately when a `step()` produces a capture, and no further `step()` calls mutate state afterward.
  - [ ] Episode sets `is_terminated == True` exactly when turn count reaches `GameConfig.max_moves` (35) with no capture, and not one turn earlier/later.
  - [ ] `history` after a full episode contains one entry per resolved turn, in order, each recording the two submitted actions and the resulting `TurnResult`.
  - [ ] **Determinism (FR7)**: `replay(actions)` run twice against a fresh episode from the same starting state and the same recorded action sequence produces identical `history` output both times (byte/value-equal).
- [ ] Run tests and confirm they **fail**.
- [ ] **Implement** `src/engine/game_loop.py` — `GameEpisode` with `reset()`, `step()`, `is_terminated`, `history`, `replay()`.
- [ ] Run tests and confirm they **pass**.
- [ ] Confirm `game_loop.py` is under 150 lines.

## 8. Cross-Module Verification (after all modules pass individually)

- [ ] Run the full `tests/engine/` suite together and confirm all tests pass with no interaction/order-dependence issues.
- [ ] Confirm every file under `src/engine/` is ≤150 lines (re-check as a batch, not just per-module).
- [ ] Grep `src/engine/` for literal hyperparameter values (`7`, `14`, `35`, `"N"`, `"STAY"`, etc. used as magic numbers rather than sourced from `GameConfig`) and confirm none exist outside `config.py` and its own tests/fixtures.
- [ ] Manually walk one full 35-turn episode via `GameEpisode` (or a scripted sequence) to sanity-check FR6 termination fires at exactly turn 35 when no capture occurs.
- [ ] Manually walk one scripted capture-by-swap scenario end-to-end through `GameEpisode` to confirm FR5 case (b) surfaces correctly at the episode level, not just inside `resolver.py`'s unit tests.

## Explicitly Out of Scope for This TODO

Per `PRD_01_Base_Logic.md`: no networking, no FastMCP, no LLM agents, no pheromone/scoring/league logic, no UI. Any task touching those belongs to a future phase's own PRD → PLAN → TODO cycle.
