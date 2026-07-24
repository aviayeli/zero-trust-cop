# PLAN — Phase 2: MCP Server

Derived from `docs/PRD_02_MCP_Server.md`. Defines the software architecture only. No code and no `TODO.md` yet — awaiting approval.

## Design Principles Applied

- **Simplicity First / Surgical Changes**: this phase adds one new package, `src/mcp_server/`, that *composes* the locked Phase 1 engine through its existing public interfaces only. Nothing under `src/engine/` is touched. No scoring, no pheromones, no networking beyond `stdio`, no agent strategy — all deferred per the PRD's Out of Scope.
- **150-line limit**: the server's three concerns — turn-buffering/timeout state, payload shaping, and tool wiring — are natural seams and are split into three modules for exactly that reason (see Module Architecture). Each stays well under the limit; if any approaches it during implementation, it must be split further before it is exceeded, not after.
- **No hardcoded hyperparameters**: `response_timeout_sec`, `watchdog_timeout_sec`, and `move_set` are loaded from `config/game.json` at server startup, never inlined. See the config-access note under `server.py` below for how this is done without modifying `engine.config`.
- **Strict TDD**: this PLAN's job is to define module boundaries, the buffering/timeout algorithm, and tool schemas precisely enough that `TODO.md` can sequence failing tests — including concurrency and timeout tests — before any implementation.
- **Engine composed, not modified**: every engine access goes through `engine.config.load_config`, `engine.game_loop.GameEpisode`, `engine.actions.parse_action`, `engine.errors.InvalidActionError`, and `engine.resolver.TurnResult` — their existing public surface, unchanged. `GameEpisode` does not expose *why* a match terminated; this phase derives `terminal_reason` itself (see below) rather than asking the engine to change.

## Verification Note — `GameConfig` and `network_and_league`

`src/engine/config.py`'s `GameConfig` dataclass currently exposes `grid_size, cop_start, thief_start, move_set, max_barriers, max_moves, survival_threshold`. It does **not** yet expose `network_and_league.response_timeout_sec` or `watchdog_timeout_sec` — those live in `config/game.json` but are not read by `load_config`. Since the engine is locked and this phase may not modify it, `server.py` obtains the two timeout values via its own minimal, config-driven read of `config/game.json` (same file, same keys, no literal fallback), separate from — but alongside — its call to `engine.config.load_config` for the engine-facing fields. This keeps every tunable sourced from `config/game.json` per `CLAUDE.md` without editing `engine/config.py`. (Whether to instead propose a small additive field on `GameConfig` in a future Phase 1 addendum is listed as an Open Item below — out of scope for this PLAN to decide unilaterally since it would touch a locked module.)

## MatchState Buffering + Non-Blocking Timeout Algorithm (locked)

This is the authoritative mechanism every module below must implement identically to `PRD_02_MCP_Server.md` FR6–FR10.

### 1. The 2-slot buffer

`MatchState` holds exactly one pending action per role for the *current* turn: `cop_action` and `thief_action`, both `None` at the start of each turn (construction, and again immediately after each resolved turn).

### 2. `submit(role, token)` flow

Given a role (`"cop"` or `"thief"`) and a raw action token:

1. **Validate role.** If `role` is not `"cop"` or `"thief"`, reject immediately — no slot touched, no deadline touched, no engine call.
2. **Validate token.** Call `engine.actions.parse_action(token)`. If it raises `InvalidActionError`, propagate the rejection — no slot touched, no deadline touched.
3. **Reject double-submission (FR7).** If this role's slot is already filled for the current (unresolved) turn, reject with an "already submitted" outcome — the existing buffered action is left untouched, the deadline is left untouched, no engine call.
4. **Fill the slot.** Store the parsed `Action` (or its token — see `server.py` note on what `MatchState` stores) in the role's slot.
5. **First-of-turn deadline.** If this is the *first* action buffered for the turn (the other slot was empty before step 4), record `deadline = clock.monotonic() + response_timeout_sec`. The deadline is not touched by the second submission.
6. **Resolve-or-wait.**
   - If, after step 4, **both** slots are filled: call `GameEpisode.step(cop_token, thief_token)` **exactly once**, capture the returned `TurnResult`, clear both slots and the deadline (reset for the next turn), and return a **resolved** outcome carrying the `TurnResult` plus updated `turn_count`/`is_terminated`.
   - Otherwise: return a **waiting** outcome — the action was accepted and buffered, the episode has not advanced.

### 3. Non-blocking timeout (the stdio nuance)

`make_move` **must never block or sleep** waiting for the other client — `stdio` is a shared, synchronous transport and a blocking handler would stall both clients' connections, not just the slow one. Instead:

- **Wall-clock deadline, not a wait.** The deadline set in step 5 above (`time.monotonic()`-based, so it is immune to system-clock adjustments) is *bookkeeping only* — nothing waits on it at submission time.
- **Lazy evaluation (primary mechanism).** Every subsequent call into `MatchState` — another `submit()`, or a read via the status/observation path — first checks: is a turn currently half-filled (exactly one slot occupied) **and** `clock.monotonic() > deadline`? If so, the half-filled turn is marked **timed-out** before doing anything else: the stale slot is cleared, the deadline is cleared, and the outcome reflects a forfeited turn (mechanism only — no scoring consequence is computed here, per PRD FR9). This is the **primary** path: it costs nothing extra (a monotonic-clock comparison) and guarantees the check happens on the very next interaction from *either* client, with no dedicated background thread.
- **Watchdog (secondary, optional).** A longer-horizon liveness concern — a client that stops calling *any* tool at all, so the lazy check above never fires — is addressed by `watchdog_timeout_sec` (60s vs. the 30s per-turn `response_timeout_sec`). This PLAN specifies the watchdog as an *optional*, out-of-critical-path background check (e.g. a periodic `asyncio` task the server may run) that performs the same lazy-style comparison against a longer deadline, purely to bound how long a fully-stalled match can sit un-forfeited. It is secondary because Phase 2's tool surface has no "push" mechanism to a client that isn't calling in — the watchdog can only mark state, it cannot notify anyone. Implementation detail (whether the watchdog thread/task ships in Phase 2 or is deferred) is an Open Item; the lazy-check path alone already satisfies FR9's mechanism requirement.
- **No `time.sleep` anywhere in a tool handler.** Both paths above are non-blocking: a comparison against `clock.monotonic()`, never a wait.

### 4. Concurrency

Two independent clients may call `make_move`, `get_observation`, and `get_match_status` concurrently over `stdio`. `MatchState`'s read-modify-write sequence (slot check → slot fill → both-filled check → `GameEpisode.step` call → slot clear) must be atomic with respect to itself: two near-simultaneous second-submissions must not both observe "both slots filled" and both call `step`.

- **Chosen guard: a single `asyncio.Lock` owned by `MatchState`, held for the full duration of `submit()`'s critical section** (steps 1–6 above), acquired via `async with`. FastMCP's tool handlers run on an `asyncio` event loop; an `asyncio.Lock` is the idiomatic single-writer primitive in that runtime and composes correctly with `await`-ing `GameEpisode.step` being called from inside the lock (note `GameEpisode.step` itself is synchronous/fast — no `await` occurs *inside* it — so the lock is held only briefly per call, never across a client round-trip).
  - Alternative considered: a plain `threading.Lock` guarding a fully synchronous critical section. Rejected as the primary choice because FastMCP tool handlers are `async def` by convention and mixing a blocking `threading.Lock` into an async handler risks stalling the event loop if contended; `asyncio.Lock` is the correct match for the runtime. (If `TODO.md`'s implementation finds FastMCP's handlers are in fact synchronous, this decision should be revisited then — not now.)
  - The lock guards **all** `MatchState` mutation *and* the `GameEpisode.step` trigger together, so "check both slots filled" and "call step" happen as one atomic unit — this is what guarantees exactly one `step` per turn (PRD FR8).
- Read-only tools (`get_observation`, `get_match_status`) also acquire the same lock briefly (to perform the lazy timeout check and to read a consistent snapshot) but never trigger `step`.

### 5. Determinism (FR10)

Wall-clock time governs *when* — or *whether* — a turn's timeout fires, and that is inherently nondeterministic (it depends on real elapsed time between client calls). This nondeterminism is strictly confined to the buffering layer: it can affect whether a turn resolves normally or is marked timed-out, but it **never** changes what `GameEpisode.step(cop_token, thief_token)` computes once both tokens are in hand. Phase 1's FR7 guarantee — identical `(cop_token, thief_token)` against identical episode state always produces an identical `TurnResult` — is untouched. Put differently: timing is a gate on *whether/when* `step` fires, never an input to it.

### 6. Deriving `terminal_reason`

`GameEpisode` exposes `is_terminated`, `turn_count`, and `history` (list of `TurnRecord`, each with `.result: TurnResult`), but not *why* the match ended. `MatchState` (or the `observations.py` view built from it — see below) derives it after every resolved turn:

```
if not episode.is_terminated:
    terminal_reason = None
elif episode.history and episode.history[-1].result.captured:
    terminal_reason = "capture"
elif episode.turn_count >= config.max_moves:
    terminal_reason = "max_moves_reached"
else:
    terminal_reason = None   # terminated but neither condition matched (defensive; should not occur)
```

`captured` is checked first because a captured turn can, in principle, coincide with the final allowed move; capture takes precedence as the more specific reason, matching Phase 1's own termination check order in `GameEpisode.step` (`captured` short-circuits before the `max_moves` check).

## Module Architecture

```
zero-trust-cop/
├── CLAUDE.md
├── config/
│   └── game.json
├── docs/
│   ├── PRD_01_Base_Logic.md
│   ├── PLAN.md
│   ├── PRD_02_MCP_Server.md
│   ├── PLAN_02_MCP_Server.md   (this document)
│   └── TODO.md                  (unchanged; Phase 2 tasks not yet added)
├── src/
│   ├── engine/                  (locked — unchanged by this phase)
│   │   └── ...
│   └── mcp_server/
│       ├── __init__.py
│       ├── match_state.py       # MatchState: 2-slot buffer, lock, deadline, submit/resolve, terminal_reason
│       ├── observations.py      # pure functions: engine/MatchState state -> tool return payload dicts
│       └── server.py            # FastMCP instance, config loading, 3 @tool wrappers, stdio entrypoint
└── tests/
    ├── engine/                  (unchanged)
    └── mcp_server/               (next step, not yet created)
        ├── test_match_state.py
        ├── test_observations.py
        └── test_server.py
```

## Module Responsibilities & Interfaces

### `match_state.py`
- **Owns**: the per-turn 2-slot action buffer, the concurrency lock, the wall-clock deadline bookkeeping, the `submit`/resolve logic that calls `GameEpisode.step` exactly once when both slots fill, the lazy timeout check, and `terminal_reason` derivation. This is the only module that mutates match-turn state or calls `GameEpisode.step`.
- **Exposes**: a `MatchState` class, constructed as `MatchState(episode: GameEpisode, response_timeout_sec: float, clock=time.monotonic)` — the clock is injectable (defaults to `time.monotonic`) so timeout behavior is unit-testable deterministically without real waiting (see Test Strategy). Public surface:
  - `async submit(role: str, token: str) -> SubmitOutcome` — implements the flow in the locked algorithm above. `SubmitOutcome` is a small dataclass/enum-tagged result distinguishing `rejected` (bad role/token/double-submit, with a reason string), `waiting`, and `resolved` (carrying the `TurnResult`).
  - `pending_roles() -> list[str]` — which role(s), if any, have a buffered-but-unresolved action for the current turn (used by `get_match_status`, FR5). Performs the lazy timeout check first.
  - `terminal_reason() -> str | None` — the FR5/derivation logic above, read-only, no mutation.
  - Read-only passthrough accessors used by `observations.py`: `turn_count`, `is_terminated`, `cop_position`, `thief_position`, `barrier_count`, wrapping the underlying `GameEpisode`/`Board` fields so `observations.py` never imports `engine.game_loop` directly (keeps the engine-composition boundary in one place).
- **Depends on**: `engine.game_loop.GameEpisode`, `engine.actions.parse_action`, `engine.errors.InvalidActionError`, `engine.resolver.TurnResult`, the standard-library `asyncio`/`time`.
- **Used by**: `server.py`'s tool wrappers.
- **150-line justification**: this module is deliberately the most complex one (it is the "locked mechanism"), but its logic is a single linear `submit()` flow plus three small read accessors — no schema shaping, no FastMCP/tool concerns, no config parsing live here. That isolation is what keeps it under the limit.

### `observations.py`
- **Owns**: pure functions that shape a `MatchState`/`GameEpisode` snapshot into the exact dict payloads the three tools return (see Tool Schemas below). No I/O, no locking, no engine mutation — every function takes already-fetched values (or a `MatchState` reference for read-only calls) and returns a plain `dict`. This isolates schema shaping so it is testable without a live server or a live episode, per PRD's testability intent.
- **Exposes**:
  - `build_observation(match_state: MatchState, config: GameConfig, role: str) -> dict` — the `get_observation` payload (own position, `turn_count`, `is_terminated`, `grid_size`, `barrier_count`; excludes the opponent's position per FR3).
  - `build_move_waiting(role: str) -> dict` — the "waiting" shape for `make_move`.
  - `build_move_resolved(match_state: MatchState, result: TurnResult, role: str) -> dict` — the "resolved" shape for `make_move`.
  - `build_move_error(reason: str) -> dict` — the shared error shape for invalid role/direction/double-submit.
  - `build_status(match_state: MatchState) -> dict` — the `get_match_status` payload (`turn_count`, `is_terminated`, `pending_roles`, `terminal_reason`).
- **Depends on**: `match_state.py` (for read-only accessors), `engine.resolver.TurnResult` (type only).
- **Used by**: `server.py`'s tool wrappers.
- **150-line justification**: five small, single-purpose pure functions, each a handful of lines of dict construction — no branching complexity beyond field selection. Comfortably under the limit; would only approach it if a function tried to do more than one tool's shaping, which is explicitly avoided by the one-function-per-shape split.

### `server.py`
- **Owns**: the `FastMCP` instance, config loading at startup (`engine.config.load_config` for engine-facing fields, plus the minimal direct `config/game.json` read for `response_timeout_sec`/`watchdog_timeout_sec` per the Verification Note above), constructing the single `GameEpisode` and single `MatchState` for the server's lifetime, the three `@tool`-registered async functions, and the `stdio` transport entrypoint (`mcp.run(transport="stdio")` or equivalent). Tool functions are **thin**: validate argument shape/type at the boundary, delegate to `MatchState`/`observations.py` for everything else, and never contain buffering, locking, or schema-shaping logic themselves.
- **Exposes**: module-level `mcp` (the `FastMCP` instance) and a `main()`/`if __name__ == "__main__":` entrypoint that runs the stdio server. No class surface beyond what `FastMCP` itself provides.
- **Depends on**: `match_state.py`, `observations.py`, `engine.config.load_config`, `fastmcp` (or the project's chosen MCP SDK — see Open Items).
- **Used by**: run directly as the server process; not imported by tests except for the thin smoke test (see Test Strategy).
- **150-line justification**: three tool functions of a handful of lines each (arg validation + one delegated call + return), plus startup wiring (config load, episode/`MatchState` construction, `mcp.run`). No buffering or shaping logic lives here, so it stays small regardless of how many tools exist within the fixed set of 3.

## Data Flow (per turn)

```
Client A: make_move(role_A, token_A)
  → server.py validates role/token shape, calls match_state.submit(role_A, token_A)
      → [lock acquired]
      → lazy timeout check on current turn (clears any stale half-filled turn first)
      → role/token validated (parse_action) — reject on failure, no mutation
      → double-submission check — reject on failure, no mutation
      → slot_A filled; if slot_B was empty, deadline = clock.monotonic() + response_timeout_sec
      → both slots filled? → NO → [lock released] → return "waiting"
      → [lock released]
  → server.py calls observations.build_move_waiting(role_A) → tool returns waiting payload

Client B: make_move(role_B, token_B)   (some time later, before deadline)
  → server.py validates role/token shape, calls match_state.submit(role_B, token_B)
      → [lock acquired]
      → lazy timeout check (deadline not yet passed — no-op)
      → role/token validated; not a double-submission
      → slot_B filled → both slots now filled
      → GameEpisode.step(cop_token, thief_token) called exactly once → TurnResult captured
      → both slots cleared, deadline cleared
      → terminal_reason derived if episode.is_terminated
      → [lock released] → return "resolved" + TurnResult
  → server.py calls observations.build_move_resolved(match_state, result, role_B) → tool returns resolved payload

Either client, any time: get_observation(role) / get_match_status()
  → server.py calls match_state read accessors (lock briefly held for lazy timeout check + snapshot)
  → server.py calls observations.build_observation / build_status → tool returns payload
```

## Concurrency & Determinism Strategy

- **Single writer, one lock.** All `MatchState` mutation and every `GameEpisode.step` invocation happen inside the one `asyncio.Lock`'s critical section, guaranteeing exactly one `step` call per turn regardless of how the two clients interleave their calls (FR8).
- **No blocking waits.** No tool handler ever calls `time.sleep` or blocks on the opponent; timeout is a lazy, deadline-comparison check performed on the next call from either side, with an optional background watchdog as a secondary net for fully-stalled matches (see locked algorithm §3).
- **Nondeterminism is confined to timing, never to resolution.** `GameEpisode.step`'s output for a given `(cop_token, thief_token)` pair against a given episode state is exactly what Phase 1's FR7 guarantees, unconditionally of when or under what contention the call happened to fire (FR10).
- **Engine state stays canonical.** `MatchState` never duplicates or shadows engine state beyond the two pending action slots and the deadline; positions, turn count, and termination are always read live from the one `GameEpisode` instance, so there is never a second source of truth to keep in sync.

## Tool Schemas

All three tools are registered on the single `FastMCP` instance in `server.py`. `role` is always the string `"cop"` or `"thief"`.

### `get_observation(role: str) -> dict`

Success (role's own view; opponent position excluded per FR3):
```json
{
  "role": "cop",
  "position": [0, 0],
  "turn_count": 4,
  "is_terminated": false,
  "grid_size": 7,
  "barrier_count": 3
}
```
Error (invalid role — rejected before touching `MatchState`/engine):
```json
{ "error": "invalid_role", "message": "role must be 'cop' or 'thief', got 'referee'" }
```

### `make_move(role: str, direction: str) -> dict`

**Waiting** (first submitter this turn):
```json
{
  "status": "waiting",
  "role": "cop",
  "message": "action buffered; waiting for thief"
}
```
**Resolved** (second submitter this turn — `GameEpisode.step` fired):
```json
{
  "status": "resolved",
  "role": "thief",
  "cop_position": [1, 0],
  "thief_position": [3, 4],
  "captured": false,
  "turn_count": 5,
  "is_terminated": false,
  "terminal_reason": null
}
```
**Error** (invalid role, invalid direction token, or double-submission — none of these buffer anything or mutate state):
```json
{ "error": "invalid_direction", "message": "Invalid action: NE" }
{ "error": "already_submitted", "message": "cop already submitted an action for this turn" }
```

### `get_match_status() -> dict`

Mid-match, one role pending:
```json
{
  "turn_count": 5,
  "is_terminated": false,
  "pending_roles": ["cop"],
  "terminal_reason": null
}
```
Terminated by capture:
```json
{
  "turn_count": 12,
  "is_terminated": true,
  "pending_roles": [],
  "terminal_reason": "capture"
}
```
Terminated by move limit:
```json
{
  "turn_count": 35,
  "is_terminated": true,
  "pending_roles": [],
  "terminal_reason": "max_moves_reached"
}
```

No point/score values appear in any payload above, per PRD FR5's explicit exclusion.

## Test Strategy (per TDD, detail belongs in TODO.md)

- **`observations.py`** is pure functions over plain inputs — every `build_*` function is unit-testable with hand-built `MatchState`/`TurnResult`-shaped fixtures, no live server or live episode required.
- **`match_state.py`** is unit-testable by constructing `MatchState` around a *real* `GameEpisode` (Phase 1's own test fixtures/config apply directly — no engine mocking needed, since composing the real engine is cheap and deterministic) plus an **injectable clock** (a simple counter/stub replacing `time.monotonic`). This makes deadline/timeout behavior deterministic and instant to test: advance the fake clock past `response_timeout_sec` between two `submit()` calls and assert the half-filled turn is cleared, with no real waiting in the test suite. Concurrency (FR8) is tested by driving two `submit()` coroutines concurrently (e.g. `asyncio.gather`) against a shared `MatchState` and asserting exactly one `GameEpisode.step` fired (spy/count on the episode) and no action was lost.
- **`server.py`** gets a thin smoke test only: the `FastMCP` instance registers exactly 3 tools with the expected names, and startup config-loading wires the right values into `MatchState` — not a full stdio integration test (out of scope for unit-level TDD; a manual/integration check belongs in `TODO.md` if desired).
- Every FR in `PRD_02_MCP_Server.md` gets a corresponding failing test before its implementation, mirroring Phase 1's discipline — exact test-to-FR mapping is `TODO.md`'s job, not this PLAN's.

## Open Items for TODO.md

- Exact ordering/granularity of TDD tasks per module (likely `match_state.py` first as the core mechanism, then `observations.py`, then `server.py` wiring last).
- Confirm the MCP SDK dependency (`fastmcp` package name/version) to add to `pyproject.toml`, and whether FastMCP tool handlers are in fact `async def` in the chosen SDK version — this PLAN assumes so and picks `asyncio.Lock` accordingly (see locked algorithm §4); revisit if not.
- Decide whether the watchdog background check ships in Phase 2 or is deferred to a later phase, given the lazy-check path alone satisfies FR9's mechanism requirement.
- Decide on the small, config-driven `response_timeout_sec`/`watchdog_timeout_sec` reader in `server.py` (direct JSON read of `config/game.json`) vs. proposing a minimal additive field on `engine.config.GameConfig` in a separate, explicitly-approved Phase 1 addendum — this PLAN defaults to the former to keep `src/engine/` untouched.
- Fixture/config strategy for `tests/mcp_server/` (reuse Phase 1's test-config fixture approach vs. a Phase 2-specific one).
- Exact `SubmitOutcome` shape (dataclass vs. tagged dict) — left as an implementation detail for `TODO.md`/code, not architecture.

## Approval Gate

Per the document lifecycle in `CLAUDE.md`, no implementation code and no `TODO.md` task list for Phase 2 is written until this architecture is approved.
