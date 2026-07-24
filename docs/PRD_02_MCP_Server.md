# PRD 02 — MCP Server (Phase 2)

## Status
Draft — Phase 2 only. Builds on the locked, tested Phase 1 engine (`docs/PRD_01_Base_Logic.md`). No LLM agent strategy, no scoring, no networking beyond local stdio.

## Objective
Expose the Phase 1 `GameEpisode` engine to two independent, asynchronous MCP clients — a Cop client and a Thief client — over a `FastMCP` server running on `stdio` transport. The engine's `step(cop_token, thief_token)` method is a single atomic call that requires both roles' actions at once; two independent clients cannot jointly make one call. This PRD defines the server's `MatchState` buffering mechanism that reconciles that mismatch: it holds the first-arriving role's action until the second arrives, then resolves the turn exactly once. The Phase 1 engine is composed unchanged — this phase adds a driving layer around it, not changes inside it.

## Scope
In scope:
- A `FastMCP` server, `stdio` transport, located in `src/mcp_server/`.
- Exactly 3 exposed MCP tools: `get_observation`, `make_move`, `get_match_status`.
- A `MatchState` buffering mechanism that accepts one action per role per turn and resolves the turn via a single `GameEpisode.step()` call once both roles have submitted.
- Concurrency-safe access to `MatchState` for two independent, concurrently-calling clients.
- Timeout mechanism referencing existing config values (`response_timeout_sec`, `watchdog_timeout_sec`) for how long the server waits on the second role.
- Partial-observability shaping of `get_observation`'s return payload (own position only, not the opponent's).

Out of scope (future phases): see "Out of Scope" section below.

## Source of Truth
All parameters are read from `config/game.json` at runtime — none may be hardcoded in implementation code, per `CLAUDE.md`. This phase reuses the existing `network_and_league` block (`response_timeout_sec: 30`, `watchdog_timeout_sec: 60`) and the existing `movement_and_barriers.move_set` — no new timeout or move-token literals are introduced.

## Functional Requirements

### FR1 — Server Composition & Transport
- The server is implemented as a `FastMCP` instance served over `stdio` transport, living under `src/mcp_server/`.
- The server holds exactly one `GameEpisode` instance (constructed from `GameConfig` loaded from `config/game.json`) for the lifetime of a match.
- The server composes `src/engine/game_loop.py` (`GameEpisode`) and its dependencies (`engine.actions.parse_action`, `engine.errors.InvalidActionError`, etc.) through their existing public interfaces only. No engine module is modified and no engine internals (e.g. `Board._barriers`) are accessed directly.

### FR2 — Tool Surface
- The server exposes **exactly 3** MCP tools: `get_observation`, `make_move`, `get_match_status`. No other tools (e.g. barrier placement, reset, admin controls) are exposed in Phase 2.

### FR3 — `get_observation(role)`
- `role` must be `"cop"` or `"thief"`; any other value is rejected with a clear error before touching `MatchState` or the engine, and does not mutate state.
- On a valid role, returns that role's observation of the current match state, derived only from what `GameEpisode` exposes:
  - the requesting role's own `(row, col)` position (`cop_state.position` or `thief_state.position`);
  - the current `turn_count`;
  - `is_terminated` (boolean);
  - board/barrier info available to that role: `grid_size` (from config) and the board's current `barrier_count`. Barriers are engine-global state, not per-role hidden state, so both roles observe the same barrier facts.
- The opponent's exact position is **not** included in the observation payload — each role's observation reflects only what that role can act on, which is the partially-observable property that makes this a Dec-POMDP at the protocol level (Phase 1 already establishes it at the engine level via simultaneous, non-cross-visible turn submission).
- Richer partial-observability features — pheromone trails, natural-language hint text, or any other sensory signal beyond position/turn/termination/barrier facts — are explicitly **out of scope** for Phase 2 and belong to a later phase's own PRD.

### FR4 — `make_move(role, direction)`
- `role` must be `"cop"` or `"thief"`; an invalid role is rejected with a clear error before any buffering occurs.
- `direction` is validated via the engine's own `parse_action`; a token outside `{N, S, E, W, STAY}` (per config `move_set`) causes `parse_action` to raise `InvalidActionError`, which the tool surfaces as an error result without buffering anything or mutating `MatchState`.
- On a valid `(role, direction)`, the action is buffered into `MatchState` for the current turn (see FR6). Two return shapes:
  - **Waiting for opponent**: if this is the first role to submit for the current turn, the call returns without invoking `GameEpisode.step`; the response indicates the action was accepted and buffered, and that the turn is pending the other role.
  - **Turn resolved**: if this submission is the second role's action for the current turn (the other role's action is already buffered), the server calls `GameEpisode.step(cop_token, thief_token)` exactly once, clears the per-turn buffer, and the response includes the resulting turn outcome (new positions, capture flag, updated turn count, termination status) — equivalent in content to a fresh `get_observation` for the caller plus the fact that resolution occurred.

### FR5 — `get_match_status()`
- Takes no role-specific argument; returns match-wide (not role-scoped) information:
  - current `turn_count`;
  - `is_terminated` (boolean);
  - which role(s), if any, currently have a buffered action pending for the current, unresolved turn (e.g. `[]`, `["cop"]`, `["thief"]`);
  - if `is_terminated` is true, the `terminal_reason`: `"capture"` (FR5/FR6 of Phase 1, either same-cell or swap) or `"max_moves_reached"`.
- Scoring and point tallies are explicitly **out of scope** — `get_match_status` reports match progress and termination, never points, rank, or win/loss scoring.

### FR6 — `MatchState` Buffering
- `MatchState` holds at most **one** pending action per role for the current turn — a 2-slot buffer (`cop_action`, `thief_action`), both initially empty at the start of each turn.
- When a role submits via `make_move`, its slot is filled. The turn does **not** advance the underlying `GameEpisode` until both slots are filled.
- Once both slots are filled, the server calls `GameEpisode.step(cop_token, thief_token)` exactly once with the buffered tokens, then clears both slots (resets `MatchState` for the next turn) before returning.
- `MatchState` is scoped to the single `GameEpisode` the server holds (FR1) — there is one buffer per match, matching the one-episode-per-server-instance model.

### FR7 — Double-Submission Handling
- If a role calls `make_move` again for the same turn while its slot is already filled and the opponent's slot is still empty, the second call is **rejected as an error** (e.g. "action already submitted for this turn") — it does not overwrite the buffered action and does not affect the pending state.
- Rationale: Phase 1's FR7 determinism guarantee (identical inputs → identical outputs, full replay support) extends into Phase 2 as "identical *accepted* inputs → identical outcomes." Allowing silent overwrites would mean the token actually resolved into `GameEpisode.step` depends on submission timing that the opposing client cannot observe, which undermines auditability and replay of a match's turn history. Reject-on-double-submit keeps exactly one action per role per turn, decided at first commit.

### FR8 — Concurrency Safety
- Because Cop and Thief are independent clients that may call `make_move` (and other tools) concurrently over `stdio`, all reads and writes to `MatchState` (and the triggering of `GameEpisode.step`) are guarded by a lock (or equivalent single-writer mechanism) such that:
  - exactly one `GameEpisode.step` call fires per turn, even if both roles' second-submitter conditions are evaluated near-simultaneously;
  - no submitted action is lost (dropped without being buffered or rejected) or double-counted (counted into two different turns, or fed into `step` twice).

### FR9 — Timeout Handling (Mechanism Only)
- The server waits for the second role's action up to the configured `response_timeout_sec` (`network_and_league.response_timeout_sec`, currently `30`) before treating the turn as missed by the non-responding role; `watchdog_timeout_sec` (currently `60`) governs the longer-horizon liveness check for an unresponsive client across turns.
- This PRD defines the **mechanism** only: a role that misses its response window causes that turn to fail/forfeit for resolution purposes. The detailed **scoring** consequence of a forfeited turn (points, technical loss accounting per `config/game.json`'s `scoring` block) is explicitly out of scope for Phase 2 and is deferred to a later phase's PRD.
- No timeout value is hardcoded in implementation code; both values are loaded from `config/game.json` at server startup, per `CLAUDE.md`.

### FR10 — Determinism (Carried Forward)
- Given the same pair of buffered action tokens for a turn, `MatchState`'s call into `GameEpisode.step` must produce exactly the outcome Phase 1's FR7 guarantees for that `(cop_token, thief_token)` pair against the current episode state. The server introduces buffering and timing around *when* `step` is called, but never changes *what* `step` computes.

## Non-Functional Requirements
- Every new Python module in `src/mcp_server/` obeys the 150-line-per-file limit in `CLAUDE.md`; split by responsibility (e.g. server/tool wiring, `MatchState`, config loading) rather than exceeding it.
- All tunable values used by this phase (`response_timeout_sec`, `watchdog_timeout_sec`, `move_set`, and any engine-derived config already loaded by `GameConfig`) are loaded from `config/game.json`; none are literals in source.
- Strict TDD: every FR above must have a corresponding failing test written before its implementation, including concurrency and double-submission tests.
- The Phase 1 engine (`src/engine/`) is treated as locked: this phase composes it through its existing public interfaces and does not modify any file under `src/engine/`.

## Acceptance Criteria
- [ ] The MCP server starts and serves over `stdio` transport.
- [ ] Exactly 3 tools are exposed: `get_observation`, `get_match_status`, and `make_move` — no more, no less.
- [ ] A full two-client turn (Cop submits, then Thief submits, or vice versa) results in exactly one `GameEpisode.step` call and a resolved turn.
- [ ] The first role to submit for a turn is buffered and the episode does not advance (`turn_count` unchanged, `GameEpisode.step` not called) until the second role submits.
- [ ] A double submission (same role, same unresolved turn) is rejected per FR7 without overwriting the buffered action or mutating episode state.
- [ ] `MatchState` access is concurrency-safe: concurrent submissions never cause zero or two `step` calls for a single turn.
- [ ] Terminal states (`capture` and `max_moves_reached`) surface correctly via `get_match_status`, with no point/score values included anywhere.
- [ ] `get_observation(role)` excludes the opponent's position and excludes pheromone/hint data.
- [ ] All timeout and move-token values used by the server are sourced from `config/game.json`; no new literals are hardcoded.
- [ ] No engine file under `src/engine/` is modified.
- [ ] No new Python file exceeds 150 lines.
- [ ] Strict TDD is followed for every FR during implementation (failing test precedes implementation code).

## Out of Scope
The following are explicitly deferred to later phases, each with its own PRD → PLAN → TODO cycle:
- LLM agent strategy or decision-making (what action a role's agent chooses to submit).
- Tournaments, leagues, or multi-game series orchestration.
- Scoring, points, ranking, or forfeit-scoring logic (the `scoring` block in `config/game.json`).
- The pheromone system and natural-language hint text.
- Networking beyond local `stdio` (no TCP/HTTP/remote transport).
- Rate limiting (the `rate_limiter_gatekeeper` block in `config/game.json`).

## Next Steps (Document Lifecycle)
Per `CLAUDE.md`, implementation of this phase may not begin until a Phase 2 plan document (`docs/PLAN.md` update or a dedicated Phase-2 plan doc) is derived from this PRD and approved, and no task is executed until it is broken out in `docs/TODO.md`.
