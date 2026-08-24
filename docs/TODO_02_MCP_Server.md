# TODO — Phase 2: MCP Server

Derived from `docs/PLAN_02_MCP_Server.md` (approved) and `docs/PRD_02_MCP_Server.md`. Executes strict TDD per `CLAUDE.md`: for every module, its test file is written and confirmed **failing** immediately before its implementation file is written, and confirmed **passing** immediately after. No task here writes implementation code before its paired test task.

Order per the user's requested sequencing and `PLAN_02`'s dependency chain: Task 0 (authorized Phase 1 addendum) → scaffolding → `observations.py` (pure, stubbed) → `match_state.py` (the locked mechanism) → `server.py` (wiring) → cross-module verification.

Tests run with `uv run pytest`; import prefix is `engine` (not `src.engine`), matching Phase 1.

## 0. Phase 1 Addendum — extend `GameConfig` with timeout fields (AUTHORIZED reopening of locked Phase 1)

This task MODIFIES the otherwise-locked Phase 1 `src/engine/config.py` and `tests/engine/test_config.py`, under explicit user authorization, so Phase 2 can source timeouts from `GameConfig` (this SUPERSEDES PLAN_02's default "direct JSON read in server.py" — recorded here as the superseding note). Strict TDD steps:

- [x] Test first: extend `tests/engine/test_config.py` to assert `GameConfig` now exposes `response_timeout_sec == 30` and `watchdog_timeout_sec == 60`, loaded from `config/game.json`'s `network_and_league` block. Keep all existing config assertions intact.
- [x] Run tests, confirm the NEW assertions **FAIL** (fields don't exist yet) — RED (`AttributeError`).
- [x] Implement: add the two fields to the `GameConfig` dataclass and read them from `data["network_and_league"][...]` in `load_config`. Additive only — do not change existing fields or their parsing.
- [x] Run tests, confirm **GREEN**, and confirm the FULL existing suite (63 prior tests + new) all pass — the additive change breaks nothing. *(Verified: 63 passed; `game.json` already had the fields so it was left untouched; `GameConfig` constructed only in `load_config`, no other site broken by the new required fields.)*
- [x] Confirm `config.py` still under 150 lines (48 lines).

Note: adding required dataclass fields means every `GameConfig(...)` construction must supply them; verify the only construction site is `load_config` (Phase 1 tests build config via `load_config`, so they remain green). Also note the existing missing-key test still raises `KeyError` (`grid_size` is accessed first, before `network_and_league` is ever reached).

## 1. Scaffolding for `src/mcp_server/`

- [x] Create `src/mcp_server/__init__.py` (empty package marker). Do **NOT** create `tests/mcp_server/__init__.py` — per the Phase 1 lesson (Task 1 note in `docs/TODO.md`), a `tests/mcp_server` package would collide with the `src/mcp_server` package name under pytest the same way `tests/engine` collided with `src/engine`; keep `tests/mcp_server/` package-free, relying on the existing `--import-mode=importlib` config.
- [x] Add the `fastmcp` (or chosen MCP SDK, per PLAN_02 Open Items) dependency to `pyproject.toml`. *(Resolved: official MCP SDK `mcp>=1.28.1`, which provides `mcp.server.fastmcp.FastMCP`. Finding for Task 3: FastMCP supports BOTH `async def` and plain `def` tool handlers — validated by `is_async`/`_is_async_callable` in `mcp/server/fastmcp/tools/base.py` and the conditional `await` in `func_metadata.py` — so PLAN_02's `asyncio.Lock` choice is viable if handlers are `async def`; `threading.Lock` remains an option if sync.)*
- [x] Confirm the test runner discovers `tests/mcp_server/` and executes with zero collected tests and no errors (sanity check before any test content exists). *(Conductor fix: `testpaths` was `["tests/engine"]`, which would NOT collect `tests/mcp_server/` on a bare `uv run pytest` — changed to `["tests"]`; verified a probe test in `tests/mcp_server/` is now collected (64 with probe, 63 without). Without this, Task 2's RED/GREEN runs would have silently skipped the new tests.)*

## 1.5 Global Multi-Agent Environment Setup (machine-level; no secrets committed)

This section configures a GLOBAL, OS-level multi-agent routing environment with LLM-Blender-style ensembling of `gemini` and `codex-agent` CLI wrappers. This is a MACHINE-LEVEL change applied by the user outside this repository — no part of it is committed here.

- [x] Anthropic/Claude access continues via the existing Ubuntu CLI login (`claude_cli`) and requires NO API key in the environment.
- [x] Provide (in a later execution step, not now) a setup script or `~/.bashrc`/`~/.zshrc` block that exports ONLY the placeholder env-var names `OPENAI_API_KEY` and `GEMINI_API_KEY`, whose actual values live in a machine-level location the user controls (their shell profile or a git-ignored `.env`), NEVER in a tracked repo file.
- [x] Establish global shell aliases `gemini` and `codex-agent` that wrap the respective CLI tools and read their credentials from the environment variables above (never from inline literals).
- [x] If a `.env` approach is used, keep it git-ignored (the repo already ignores `.env`) and commit only a `.env.example` containing blank placeholders (`OPENAI_API_KEY=` / `GEMINI_API_KEY=`), never real values.
- [x] Verification — confirm `git status` shows no secret-bearing file staged, and grep the repo to confirm no literal key/token string is ever committed.

**Security invariant:** No literal API keys, tokens, or secrets are ever written to any file tracked by this repository. Only placeholder env-var names appear here; real values live only in the user's machine-level environment.

## 2. `observations.py` (pure view functions) — FIRST per user's requested order

Dependency nuance: `observations.py`'s functions reference a `MatchState` (which is built in Task 3, later). To honor strict TDD and the user's observations-first ordering, its failing tests are written against **duck-typed stub fixtures** — a tiny fake object exposing the same read accessors as the real `MatchState` (`turn_count`, `is_terminated`, `cop_position`, `thief_position`, `barrier_count`, `pending_roles`, `terminal_reason`) — plus plain `TurnResult`-shaped values, **not** the real `MatchState`. This lets `observations.py` be built and tested before `match_state.py` exists. `observations.py` uses string/deferred type annotations for its `MatchState` parameter so the module does not import a non-existent `MatchState` at module load time.

- [x] Test first: write `tests/mcp_server/test_observations.py` asserting the exact dict schemas from `PLAN_02_MCP_Server.md`'s Tool Schemas section:
  - [x] `build_observation(stub_match_state, config, role)` returns the own-position-only shape (`role`, `position`, `turn_count`, `is_terminated`, `grid_size`, `barrier_count`) — excludes the opponent's position.
  - [x] `build_move_waiting(role)` returns `{"status": "waiting", "role": ..., "message": ...}`.
  - [x] `build_move_resolved(stub_match_state, result, role)` returns `{"status": "resolved", "role", "cop_position", "thief_position", "captured", "turn_count", "is_terminated", "terminal_reason"}`.
  - [x] `build_move_error(reason)` returns the shared `{"error": ..., "message": ...}` shape for invalid role / invalid direction / double-submission cases.
  - [x] `build_status(stub_match_state)` returns `{"turn_count", "is_terminated", "pending_roles", "terminal_reason"}` — no scoring fields anywhere.
- [x] Run tests, confirm they **FAIL** (module does not exist yet) — RED (`ModuleNotFoundError`).
- [x] Implement `src/mcp_server/observations.py` — five pure functions only, no locking/IO/engine-mutation, matching `PLAN_02`'s Module Responsibilities & Interfaces for `observations.py` exactly. *(Verified: duck-typed, uses `from __future__ import annotations` — no `engine`/`match_state` import at load; opponent position excluded for both roles; Conductor independently exercised all 5 functions against PLAN_02 schemas.)*
- [x] Run tests, confirm **GREEN**; confirm full suite (Phase 1 engine tests + new observations tests) green (15 passed; full suite 78 passed).
- [x] Confirm `observations.py` is under 150 lines (76 lines).

## 3. `match_state.py` (the locked mechanism; depends on the real `GameEpisode` + injectable clock)

- [x] Test first: write `tests/mcp_server/test_match_state.py` covering, per `PLAN_02`'s locked algorithm:
  - [x] The 2-slot buffer: `MatchState` starts with both `cop_action`/`thief_action` slots empty.
  - [x] First `submit(role, token)` this turn returns a **waiting** outcome and does **not** advance the episode (`GameEpisode.step` not called).
  - [x] Second `submit(role, token)` this turn triggers exactly one `GameEpisode.step` call and returns a **resolved** outcome carrying the `TurnResult`; both slots and the deadline are cleared afterward.
  - [x] Invalid role is rejected — no slot touched, no deadline touched, no engine call.
  - [x] Invalid direction token (via `parse_action` raising `InvalidActionError`) is rejected — no slot touched, no mutation.
  - [x] Double-submission (same role submits twice before the turn resolves) is rejected — no overwrite of the existing buffered action, no mutation.
  - [x] Lazy timeout via an **injected fake clock**: buffer one role's action, advance the fake clock past `response_timeout_sec`, then make the next call (a `submit` or a read accessor) and confirm the stale half-filled turn is cleared/forfeited before that call proceeds — no real `time.sleep` anywhere in the test.
  - [x] `terminal_reason()` derivation: a resolved capture turn yields `"capture"`; a resolved turn at `turn_count == max_moves` with no capture yields `"max_moves_reached"`; a non-terminated match yields `None`.
  - [x] Concurrency (FR8): two `submit()` coroutines driven concurrently via `asyncio.gather` against a shared `MatchState` resolve to exactly one `GameEpisode.step` call — no lost action, no double-counted action (spy/count on the episode's `step`).
  - [x] Determinism check: the `TurnResult` produced via `MatchState.submit` matches what a direct Phase-1 `GameEpisode.step(cop_token, thief_token)` call produces for the same inputs against an equivalent fresh episode.
- [x] Run tests, confirm they **FAIL** — RED.
- [x] Implement `src/mcp_server/match_state.py` per the locked algorithm in `PLAN_02_MCP_Server.md`:
  - `MatchState(episode: GameEpisode, response_timeout_sec: float, clock=time.monotonic)`, `response_timeout_sec` sourced from `GameConfig.response_timeout_sec` (Task 0), never a literal.
  - `async submit(role, token) -> SubmitOutcome` guarded by a single `asyncio.Lock` held for the full critical section (steps 1–6 of the locked algorithm).
  - `pending_roles()`, `terminal_reason()`, and read-only passthrough accessors (`turn_count`, `is_terminated`, `cop_position`, `thief_position`, `barrier_count`).
  - All resolution delegated to `GameEpisode.step` — no capture logic re-implemented here.
- [x] Run tests, confirm **GREEN**; confirm full suite green (13 passed; full suite 91 passed).
- [x] Confirm `match_state.py` is under 150 lines (148 lines; trimmed from an initial 167 — Conductor caught the overflow before commit). *Timeout semantics: option (a) — stale action flushed, triggering submit becomes first of a fresh turn — approved by Conductor+Judge. asyncio.Lock concurrency verified via asyncio.gather (exactly one step).*

## 4. `server.py` (FastMCP wiring; depends on `match_state.py` + `observations.py`)

- [x] Test first: write `tests/mcp_server/test_server.py` as a thin smoke test asserting:
  - [x] The `FastMCP` instance registers exactly 3 tools, named `get_observation`, `make_move`, `get_match_status`.
  - [x] Startup config-loading wires `GameConfig.response_timeout_sec` / `watchdog_timeout_sec` (from Task 0) into the constructed `MatchState`.
  - [x] Tool wrapper functions are thin — they delegate to `match_state`/`observations` and contain no buffering, locking, or schema-shaping logic themselves.
  - (Full stdio integration is a manual check, noted under Task 5, not a unit test here.)
- [x] Run tests, confirm they **FAIL** — RED.
- [x] Implement `src/mcp_server/server.py` — single module-level `FastMCP` instance (`mcp`), config load at startup (`engine.config.load_config`, now including timeouts per Task 0), one `GameEpisode` + one `MatchState` constructed for the server's lifetime, the three `@tool`-registered async wrapper functions, and a `stdio` entrypoint (`mcp.run(transport="stdio")` or equivalent). No buffering/locking/shaping logic lives in this module.
- [x] Run tests, confirm **GREEN**; confirm full suite green.
- [x] Confirm `server.py` is under 150 lines.

## 5. Cross-Module Verification (Phase 2 closeout)

- [x] Run the full `tests/` suite (`engine/` + `mcp_server/`) together and confirm all tests pass with no interaction/order-dependence issues.
- [x] Confirm every file under `src/mcp_server/` is under 150 lines (re-check as a batch, not just per-module).
- [x] Grep `src/mcp_server/` for hardcoded hyperparameters (timeout literals `30`/`60`, move tokens, grid size) and confirm none exist outside config-sourced reads (`GameConfig` fields from Task 0).
- [x] Confirm no `time.sleep` call exists anywhere in `src/mcp_server/`; confirm the concurrency test in Task 3 drives real `asyncio` (`asyncio.gather` or equivalent) and asserts exactly-one-`step`.
- [x] Confirm the lazy-deadline forfeit path is exercised via an injected clock with zero real waiting anywhere in the test suite.
- [x] Confirm no file under `src/engine/` changed beyond Task 0's authorized additive `config.py` / `tests/engine/test_config.py` edit.

## Explicitly Out of Scope for This TODO

Per `PRD_02_MCP_Server.md` and `PLAN_02_MCP_Server.md`: no LLM agent strategy, no leagues, no scoring, no pheromones/hints, no networking beyond `stdio`, no rate limiting. The watchdog background task (secondary timeout mechanism, `watchdog_timeout_sec`) is an Open Item in `PLAN_02` — its shipping in Phase 2 vs. deferral to a later phase is not decided by this TODO; the lazy-check path in Task 3 alone satisfies FR9's mechanism requirement. Any task touching deferred items belongs to a future phase's own PRD → PLAN → TODO cycle.
