# PLAN — System Architecture (Phases 1–7)

Derived from the `PRD_0*.md` series. This is the top-level architectural
specification for the completed system: a zero-trust, peer-to-peer Police–Thief
pursuit game in which two mutually distrusting FastMCP peers play a lockstep
commit–reveal match with no trusted arbiter, no shared memory, and no shared
process.

Phase-level detail lives in the per-phase documents (`PLAN_02_MCP_Server.md`,
`PLAN_03_Security.md`, `PLAN_04_Strategy.md`, `PLAN_05_Wiring_and_Training.md`,
`PLAN_06_Local_MCP_Simulation.md`, `PLAN_07_Submission_Alignment.md`). This file
is the authority on module boundaries, locked algorithms, and cross-phase
invariants; where it and a phase document disagree, this file wins.

## Design Principles Applied

- **Simplicity First / Surgical Changes**: each module owns exactly one concern.
  Composition roots (`mcp_server/server.py`, `scripts/run_local_mcp_match.py`)
  wire dependencies and hold no logic of their own.
- **150-line limit**: modules are split along natural seams *before* the limit is
  reached, not after — `tools.py` was split out of `server.py`, `log_checks.py`
  and `log_shape.py` out of `replay_match.py`, `mime_report.py` out of
  `email_sender.py`, `action_buffer.py` out of `match_state.py`,
  `match_report.py` out of `run_local_mcp_match.py`. The longest tracked
  module is `scripts/render_replay.py` at 148 lines.
- **No hardcoded hyperparameters**: every tunable lives in `config/game.json`
  (shared contract) or `config/<role>/game.toml` (per-peer strategy and
  networking). `engine/config.py` and `strategy/settings.py` are the only
  modules permitted to know those paths.
- **Strict TDD**: every module below was specified precisely enough that a
  failing test could be written before it existed. Current state: **914 tests
  passing**.

## FR5 Turn-Resolution & Tie-Break Rule (locked)

This is the authoritative resolution algorithm every layer must implement
identically to `PRD_01_Base_Logic.md` FR5. It is implemented once, in
`engine/resolver.py`, and nothing else duplicates it:

1. **Simultaneous evaluation** — compute both agents' *intended* new positions
   from the current board state, before committing either.
2. **Barrier & bounds check** — for each agent independently: if its intended
   position is off-grid or on a barrier cell, that agent's move resolves to
   `STAY`. This check is per-agent and does not depend on the other agent's move.
3. **Capture check** — after both positions are resolved:
   - a) `new_cop_pos == new_thief_pos` → capture, or
   - b) `new_cop_pos == old_thief_pos AND new_thief_pos == old_cop_pos` → capture
        (agents swapped cells / crossed paths).
4. Only a malformed action token (not one of `N/S/E/W/STAY`) is rejected as
   illegal input, prior to step 1 — it never reaches resolution.

## Module Architecture

```
zero-trust-cop/
├── CLAUDE.md
├── config/
│   ├── game.json               # shared contract: board, scoring, pheromones, league
│   ├── declaration.json         # Step-0 identity: group, members, repos, endpoints
│   ├── benchmark.json           # off-manifold probe: sample size, seed, opponents
│   ├── police/                  # peer workspace: game.json, game.toml, keys, peers/*.pub
│   └── thief/                   # peer workspace: game.json, game.toml, keys, peers/*.pub
├── docs/                        # PRD → PLAN → TODO, per phase
├── src/
│   ├── engine/                  # deterministic, offline game core (Phase 1)
│   │   ├── config.py            # loads & validates config/game.json
│   │   ├── actions.py           # Action enum/type + validity check
│   │   ├── board.py             # grid bounds + barrier placement/lookup
│   │   ├── barriers.py          # derives the layout from barrier_seed (§4.3)
│   │   ├── player.py            # agent position state + intended-move computation
│   │   ├── resolver.py          # FR5 algorithm: bounds/barrier resolution + capture
│   │   ├── game_loop.py         # episode orchestration: init, step, termination, history
│   │   └── errors.py            # shared exception types
│   ├── mcp_server/              # FastMCP peer + zero-trust protocol (Phases 2–3)
│   │   ├── server.py            # composition root: one FastMCP app per peer
│   │   ├── tools.py             # the four-tool wire surface
│   │   ├── observations.py      # observation/status payload construction
│   │   ├── submissions.py       # SubmissionGate: signature auth + stall expiry
│   │   ├── commitments.py       # CommitmentBook: the lockstep phase machine
│   │   ├── crypto.py            # SHA-256 commit/verify primitive
│   │   ├── identity.py          # Ed25519 sign/verify, key paths, PEER_ROLES
│   │   ├── keygen.py            # first-run key material generation
│   │   ├── peer_keys.py         # public-key loading by own-role workspace
│   │   ├── match_state.py       # async 2-slot turn buffer + terminal reason
│   │   ├── action_buffer.py     # the slot mechanics behind MatchState
│   │   ├── directions.py        # wire-vocabulary encode/decode + stated hints
│   │   ├── peer_client.py       # PeerClient: prepare() one signed submission
│   │   ├── peer_policy.py       # builds a match-mode AgentPolicy for a peer
│   │   ├── http_peer.py         # streamable-HTTP tool invocation
│   │   ├── rate_limiter.py      # the agreed gatekeeper throttle + retry
│   │   ├── transport.py         # [network] settings loader
│   │   ├── tunnel.py            # public_url validation/normalisation
│   │   └── repos.py             # repo + [email] settings loader
│   ├── strategy/                # the AI brain (Phase 4)
│   │   ├── qvalues.py           # tabular Q-learning + persistence
│   │   ├── fallback.py          # greedy Manhattan tie-break for unlearned states
│   │   ├── opponents.py         # scripted training opponents + `frozen`
│   │   ├── pheromones.py        # decaying scent-trail belief field
│   │   ├── belief.py            # stated-intent honesty tracker
│   │   └── settings.py          # [strategy] settings loader
│   ├── agent/agent_core.py      # AgentPolicy: the policy layer over strategy/
│   ├── gui/                     # replay viewer, live heatmap, canvas, palette
│   ├── reporting/               # Gmail transport, MIME report, send policy
│   └── scripts/                 # match loop, artifacts, reporting, verifier,
│       │                        #   tournaments, §10.10 off-manifold probe
│       ├── board_agreement.py   # pre-match board/axis check (§2, audit T-1)
│       ├── opponent_pool.py     # weighted per-episode opponent selection
│       └── train_diverse.py     # the shipped opponent-diverse trainer
└── tests/                       # 914 tests, mirroring the src/ layout
```

## 1. Engine Layer — Module Responsibilities & Interfaces

### `config.py`
- **Owns**: reading and parsing `config/game.json`; the single source of truth
  for every shared hyperparameter (`grid_size`, `cop_start`, `thief_start`,
  `move_set`, `max_barriers`, `max_moves`, `survival_threshold`, the `scoring`
  block, the `pheromones` block, the `network_and_league` block).
- **Exposes**: `GameConfig` with typed fields, and `load_config(path) -> GameConfig`.
- **Used by**: every other module — no module reads `config/game.json` directly.

### `actions.py`
- **Owns**: the fixed action vocabulary and the legal-token check (FR3 / step 4).
- **Exposes**: `Action` enum (`N, S, E, W, STAY`), `parse_action(token) -> Action`
  raising `InvalidActionError`, and the `(row, col)` delta per action.
- **Drift guard**: a test asserts `[a.name for a in Action] == GameConfig.move_set`,
  so `config/game.json` stays the source of truth without runtime coupling.

### `board.py`
- **Owns**: grid bounds and barrier state (placement, lookup, count).
- **Exposes**: `Board.in_bounds(pos)`, `is_barrier(pos)`,
  `place_barrier(pos, occupied=())` (enforces the 14-barrier cap and the
  occupancy rule), `barrier_count`. Occupancy is supplied by the caller so the
  board stays decoupled from `player.py`.

### `barriers.py`
- **Owns**: deriving the barrier layout from `barrier_seed` and `max_barriers`,
  and the connectivity invariant. Detail in §4.3.
- **Exposes**: `barrier_layout(config)`, `populated_board(config)`.

### `player.py`
- **Owns**: one agent's position state and the *pure* computation of an intended
  next position — deliberately with no bounds or barrier awareness, per FR5's
  separation of concerns.
- **Exposes**: `PlayerState(position, role)`, `intended_position(state, action)`.

### `resolver.py`
- **Owns**: the FR5 algorithm exactly as locked above. The only implementation of
  the tie-break/capture rule in the codebase.
- **Exposes**: `resolve_turn(board, cop_state, thief_state, cop_action, thief_action)
  -> TurnResult` carrying both resolved positions and `captured: bool`.

### `game_loop.py`
- **Owns**: episode orchestration — initialising agents at configured starts,
  driving one `step()` per turn through `resolver.py`, tracking turn count,
  enforcing FR6 termination (capture, or turn count reaching `max_moves`), and
  recording full history for deterministic replay (FR7).
- **Exposes**: `GameEpisode` with `reset()`, `step()`, `is_terminated`, `history`,
  `replay(actions)`.
- **Invariants**: positions are normalised to tuples (config starts are JSON
  lists, so `(0,0) == [0,0]` would otherwise be False); a `step()` on a
  terminated episode is a no-op.

### `errors.py`
- **Owns**: all engine exception types (`InvalidActionError`, `BarrierLimitError`,
  `IllegalBarrierPlacementError`) so no module raises ad hoc.

## 2. Core Communication — FastMCP Peer Isolation

### Repository isolation

Isolation is enforced at four levels, not one. The weakest of them is the one
that defines the guarantee, so all four are stated:

| Level | Boundary | Enforced by |
|-------|----------|-------------|
| Repository | Two independent GitHub repositories | `zero-trust-cop` and `zero-trust-thief`, each self-contained and separately clonable |
| Process | One OS process per peer | `peer_processes.running_peers` spawns and reaps both |
| State | One `GameEpisode`, `MatchState` and `CommitmentBook` per peer | `server.create_app` builds them per role |
| Configuration | One workspace per peer | `config/<role>/` — own `game.toml`, own `signing_key.pem`, own `peers/*.pub` |

There is **no shared memory, no shared file, and no shared database table**
between the peers at runtime. They meet only over the authenticated wire of
§2's tool surface, and neither imports the other's package.

**Cross-links (submission requirement).** Each repository's `README.md` §0
carries a direct link to the other, in both a table row and a prose callout.
Both URLs are also declared once per peer in `config/<role>/game.toml` under
`[game.repos]` and are emitted into `declaration_<game_id>.json` and
`result_<game_id>.json`, so a marker holding *either* artifact can find the
other half of the pair without consulting either README.

**Build-time propagation is not runtime coupling.** `scripts/sync_repos.sh`
rebuilds the thief branch from this repository and regenerates its README via
`scripts/thief_readme.py`, which fails loudly if any cross-link anchor stops
matching. The thief branch is *rebuilt*, never rebased, because both branches
edit README §0 and a rebase conflicts on every run — which once produced a
half-converted README with two inconsistent cross-link tables. This is a
release tool that runs on a developer machine between matches; it creates no
link between the two peers while a match is in progress.

### Topology

Two independent FastMCP servers, each in its own OS process, each with its own
config directory, its own key material, and — critically — **its own
`GameEpisode`**. There is no shared memory, no shared database, and no shared
engine instance between peers. This is the *mirrored local truth* topology (D2):
neither peer trusts the other's engine, so each keeps its own and the two are
compared every turn.

| Peer     | Engine role | Port   | Endpoint                      | Workspace        |
|----------|-------------|--------|-------------------------------|------------------|
| `thief`  | thief       | `8801` | `http://127.0.0.1:8801/mcp`   | `config/thief/`  |
| `police` | cop         | `8802` | `http://127.0.0.1:8802/mcp`   | `config/police/` |

Each peer's `[network].opponent_url` points at the other's port, and
`config/declaration.json::mcp_servers` publishes the same pair. Three
independent sources therefore encode the port assignment, and
`test_declaration_agrees_with_transport` fails if they ever drift apart.
Transport is **streamable HTTP**, not stdio, so the peers talk over a real
network transport that a remote opponent could substitute for loopback;
`tunnel.py::parse_public_url` validates an optional ngrok/Localtonet
`public_url` for league play, accepting empty (loopback-only) and rejecting
bare hosts, `tcp://`, `//host`, and host-less URLs.

### Wire surface

`tools.py` registers exactly four tools per peer. FastMCP derives each tool's
public input schema from its Python signature, so **parameter names are the
protocol** and a rename is a breaking protocol change:

| Tool                | Signature                                                     | Purpose |
|---------------------|---------------------------------------------------------------|---------|
| `get_observation`   | `(role)`                                                      | This peer's view of the board; refuses a caller claiming the wrong role. |
| `submit_commitment` | `(role, turn, h_commit, signature)`                           | Publish a binding digest for this turn. |
| `reveal_move`       | `(role, turn, state, move, intent, nonce, signature)`         | Open the commitment; resolves the turn once both are in. |
| `get_match_status`  | `()`                                                          | Turn count, positions, termination and terminal reason. |

A peer's own identity is read from the `own_role` captured at registration,
never from the caller-supplied `role` argument, so a caller cannot assume the
server's identity by asserting it.

### Cross-engine agreement

`scripts/match_loop.py::play_match` broadcasts every submission to **both**
peers, then compares the two independently-computed results on
`turn_count`, `cop_position`, `thief_position`, `captured`, and `is_terminated`.
Any mismatch raises `DivergenceError` and aborts the match. A disagreement is
raised, never absorbed — that comparison is the entire point of running two
engines, and it is what later licenses the `mutual_agreement.confirmed` flag in
the result artifact.

## 3. Cryptographic State Machine — Commit-Reveal Lockstep

### The problem

Both agents move simultaneously with no trusted arbiter. A naive
"send me your move" protocol lets whichever peer answers second choose its move
after seeing the first — a total break of simultaneity. Commit–reveal removes
that option.

### The commitment primitive (`mcp_server/crypto.py`)

```
h_commit = SHA256( State || Move || Intent || Nonce )
```

- **Positional concatenation, no delimiters** — Rulebook 5.3 specifies literal
  concatenation, so that is what is emitted. This is an interoperability
  contract with the opposing group: any divergence silently breaks cross-group
  play and *cannot be detected by either group alone*, since each verifies
  against its own serialisation. Documented caveat: field boundaries are
  positional only; the fixed-length trailing nonce and the two-word `intent`
  vocabulary bound the ambiguity in practice, but a delimited form would be
  strictly safer.
- **Nonce** — 16 bytes (128 bits) from `secrets.token_hex`, fresh per
  commitment. The nonce is what hides the move: without it, a five-element move
  set is brute-forced instantly.
- **Verification** — `verify()` recomputes the digest and compares with
  `secrets.compare_digest`, not `==`, which would leak through timing how many
  leading characters matched and hand an opponent a search gradient toward a
  colliding reveal. A superseded canonical-JSON payload form is still *accepted*
  for verification so artifacts sealed before the 5.3 alignment stay verifiable;
  nothing emits it any more.
- **Scope, stated honestly** — this proves a revealed move matches an earlier
  commitment *by whoever holds the nonce*. Authentication of *who* submitted it
  is a separate mechanism (below), and nothing here encrypts traffic.

### Authentication (`mcp_server/identity.py`)

Every submission is signed with **Ed25519** over
`canonical_json({"role", "turn", "h_commit"})` — sorted keys, no whitespace —
and transmitted as lowercase hex. Binding the turn number into the signed
message is what stops a captured signature from being replayed on a later turn.
Each peer workspace holds its own `signing_key.pem` and a `peers/<role>.pub`
directory of 32-byte raw-hex public keys; `keygen.ensure_keys` generates any
missing material on first run. `SubmissionGate` rejects an unsigned or
mis-signed submission before `CommitmentBook` ever sees it.

### Phase machine

The per-peer turn lifecycle is the six-phase cycle below. It is **not** a single
`GamePhaseMachine` class — the responsibility is deliberately split so that each
guard lives with the state it protects: the authoritative shared-turn state is
`CommitmentBook.state()`, the per-peer computation phases live in
`PeerClient.prepare`, and turn resolution lives in `MatchState`. The mapping is
exact and is what the tests pin:

| Phase                 | Implemented by                              | `CommitmentBook.state()` | Exit condition |
|-----------------------|---------------------------------------------|--------------------------|----------------|
| `WAITING_FOR_OPPONENT`| `tools.get_observation` / `MatchState`      | `empty`                  | Turn opens; observation retrieved. |
| `COMPUTING_MOVE`      | `PeerClient.prepare` → `AgentPolicy.decide` | `empty`                  | `(move, intent)` chosen from the Q-table. |
| `COMMITTING`          | `crypto.commit` → `identity.sign` → `submit_commitment` | `half` → `both_committed` | Both peers' digests are on record. |
| `AWAITING_REVEAL`     | `CommitmentBook.reveal` guard               | `both_committed`         | First reveal accepted. |
| `VERIFYING`           | `crypto.verify` + `verify_signature`        | `half_revealed` → `resolved` | Both reveals verified. |
| → `WAITING_FOR_OPPONENT` | `MatchState.submit` → `GameEpisode.step` | `empty` (turn `n+1`)     | Turn resolved, buffer cleared, turn incremented. |

**Transition rules (locked).**

1. **No reveal before both commitments.** `reveal()` returns
   `reveal_before_commit` unless `len(commitments) == len(PEER_ROLES)`. This is
   the load-bearing rule: without it the second peer could withhold its
   commitment, read the first peer's reveal, and only then commit.
2. **One commitment per role per turn.** A second attempt returns
   `already_committed`; a second reveal returns `already_revealed`.
3. **Monotonic turns.** A commitment for a turn *below* the book's current turn
   is `stale_turn`. A commitment for a turn *above* it rolls the book forward —
   clearing commitments, moves, and the deadline — so a new turn always starts
   clean.
4. **A broken commitment is fatal to that reveal.** If the revealed
   `(state, move, intent, nonce)` does not reproduce the stored digest, the
   reveal is rejected as `broken_commitment` and the move never reaches the
   engine.
5. **Blame follows the blocked phase (D7).** `stalled_roles()` starts its
   deadline at the *first* commitment. While any commitment is outstanding, only
   the silent committer is at fault — its opponent is *blocked*, not stalling,
   because rule 1 refuses its reveal. Once both commitments are in, blame moves
   to whoever has not revealed. Timeouts are `response_timeout_sec = 30`;
   `MatchState.forfeit` then records a `technical_loss`.
6. **A real outcome outranks a forfeit.** `terminal_reason()` returns `capture`
   or `max_moves_reached` from the episode's own history before it will consider
   `technical_loss`, so a late stall check cannot relabel a match that actually
   finished.
7. **One wire encoding, and the superseded one is opt-in.** `crypto.verify`
   accepted BOTH the Rulebook-5.3 positional concatenation and a superseded
   sorted-key JSON form, unconditionally. Nothing has emitted the JSON form
   since the 5.3 alignment, so on the live wire that was only attack surface:
   two encodings of the same fields, one of which this project no longer
   speaks. The fallback is now behind a **keyword-only** `allow_legacy`
   defaulting to `False`. Its one legitimate reader is verification of
   artifacts sealed before the alignment, so `scripts/log_checks.py` and
   `scripts/render_replay.py` pass it explicitly and nothing on the protocol
   path does. Keyword-only is the point: a sixth positional argument at some
   future call site cannot silently re-open the wire.

### Rejection and disqualification codes

Every refusal returns a machine-readable code rather than a free-text message,
so a peer — or a grader — can distinguish a protocol violation from a transport
failure. The codes partition into three severities:

Every refusal is shaped by `observations.build_move_error` into
`{"error": <code>, "message": …}`, so the code is the contract and the prose is
advisory. The gate checks run in a fixed order — forfeit, role, turn,
signature, vocabulary, then the book — so an unauthenticated caller can never
reach the commitment book at all:

| Code | Raised by | Phase | Severity | Meaning |
|------|-----------|-------|----------|---------|
| `invalid_role` | `SubmissionGate`, `CommitmentBook`, `MatchState`, `tools.get_observation` | any | **Rejected** | Role is not one of `("police", "thief")`, has no loaded public key, or — on `get_observation` — is not this server's `own_role`. |
| `wrong_turn` | `SubmissionGate` | `COMMITTING`, `AWAITING_REVEAL` | **Rejected** | The caller-supplied turn is not `MatchState.turn_count`. The gate treats its own turn counter as authoritative, because a caller-supplied turn could label a reveal as future work or clear a book's in-progress commitments. |
| `stale_turn` | `CommitmentBook` | `COMMITTING`, `AWAITING_REVEAL` | **Rejected** | Submission names a turn below the book's current turn (the book's own guard, behind the gate's). |
| `already_committed` | `CommitmentBook.commit` | `COMMITTING` | **Rejected** | A second commitment from a role in one turn. |
| `already_revealed` | `CommitmentBook.reveal` | `VERIFYING` | **Rejected** | A second reveal from a role in one turn. |
| `already_submitted` | `MatchState.submit` | resolution | **Rejected** | That role's buffer slot is already filled this turn. |
| `invalid_direction` | `SubmissionGate`, `MatchState.submit` | `VERIFYING`, resolution | **Rejected** | Move is outside the wire vocabulary, or fails `parse_action` after decoding. |
| `invalid_intent` | `SubmissionGate.reveal_move` | `VERIFYING` | **Rejected** | The revealed intent is not a well-formed intent string. |
| `reveal_before_commit` | `SubmissionGate`, `CommitmentBook.reveal` | `AWAITING_REVEAL` | **Protocol violation** | A reveal arrived before both commitments were on record — an attempt to break simultaneity. Guarded twice: the gate refuses when this role has no stored digest, the book refuses until *both* are present. |
| `invalid_signature` | `SubmissionGate` | `COMMITTING`, `VERIFYING` | **Protocol violation** | Ed25519 verification failed for this `(role, turn, h_commit)`. Checked before the book is touched, so a forged or replayed submission never enters protocol state. |
| `broken_commitment` | `CommitmentBook.reveal` | `VERIFYING` | **Protocol violation** | The revealed tuple does not reproduce the stored digest — an attempt to change a move after committing. The move never reaches the engine. |
| `match_forfeited` | `SubmissionGate` | any | **Disqualification** | The match already ended against a stalled peer; further submissions are refused rather than silently accepted into a dead match. |
| `technical_loss` | `MatchState.terminal_reason` | any | **Disqualification** | The peer named by `stalled_roles()` exceeded `response_timeout_sec = 30` in the phase it was blocking. Terminal for the match. |

The severities are operationally different: a **rejection** is recoverable — the
caller may correct and retry within the turn — whereas a **protocol violation**
means the submission is discarded and the turn cannot resolve from it, and a
**disqualification** ends the match. Only the last class is terminal, and even
then a real game outcome outranks a forfeit (rule 6 above), so a match that
genuinely finished can never be relabelled by a late stall check.

### Turn resolution concurrency

`MatchState` holds a two-slot action buffer guarded by a single `asyncio.Lock`.
The read-modify-step sequence runs entirely inside the lock, so **exactly one**
`GameEpisode.step` fires per turn even under concurrent submissions (FR8).
Timeout is a lazy wall-clock check (`expire_if_stale`) rather than a blocking
sleep, and the clock is injectable so timeout behaviour is deterministically
testable. Rejection codes are `invalid_role`, `invalid_direction`,
`already_submitted`.

## 4. Physical & Strategic Models

### 4.1 Thief Scent Trail (`strategy/pheromones.py`)

The thief leaves a decaying trace, and the cop reads that trace where no
revealed position is available.

**Where the field is actually used — stated up front, because the two roles are
not interchangeable.** The scent trail is deposited by exactly one caller,
`AgentPolicy.observe_opponent`, and that caller runs in exactly one place: the
**offline trainer** (`scripts/tournament_loop.play_episode`). It is read by
exactly one caller, `AgentPolicy.hybrid_opponent_cell`, and only when no
resolved opponent cell was supplied. That gives the field two concrete jobs:

1. **Offline belief substrate during policy convergence.** In training, the
   opponent's cell is withheld on turn 0 of every episode (`_last_resolved`
   returns `None`), so the state key for that turn is built from
   `PheromoneField.strongest()`. The field is *not* reset between games, so
   from game 2 onward every episode opens with a belief carried over from
   where the opponent was previously seen — a decaying, recursively-updated
   memory across the whole 2000-game series.
2. **Visualisation substrate.** `scripts/render_replay.py` rebuilds the field
   from a signed match log to drive the Tkinter and CLI heatmaps
   (`gui/live_heatmap.py`, §6.2). This is what a reader of a finished match
   sees; it is a rendering of the log, not a live input to play.

**What it is NOT.** In a live P2P league match the field is inert: the match
loop feeds `PeerClient.prepare` a resolved coordinate on every turn (§4.2), so
the fallback never fires, and a live peer's field is never even deposited into.
Nor is it a reward term — the two shaping terms the learner actually receives
are `invalid_move_penalty` and `step_cost` (§4.2), and neither consults it.
Naming this precisely is the point: an earlier draft of this document called
the field "the live belief map", which the live code path does not support.

Both constants are configured in `config/game.json`, never inlined:

| Symbol | Config key                     | Value |
|--------|--------------------------------|-------|
| τ₀     | `pheromone_center_intensity`   | `0.90` |
| ρ      | `pheromone_decay`              | `0.10` |
| window | `pheromone_grid_size`          | `5` (odd, validated) |

**Recurrence (locked).**

$$\tau(t{+}1) = \max\bigl(0,\ (1-\rho)\,\tau(t) + \delta\bigr)$$

The `max(0, …)` clamp is a hard invariant: a concentration is never negative,
including under the signed direct-delta path retained to make that clamp
testable.

**Kernel.** One observation stamps a linear Manhattan-falloff kernel over a 5×5
box with radius `r = 2` and `scale = r + 1 = 3`:

$$\delta(c) = \tau_0 \cdot \frac{\text{scale} - d_{\text{Manhattan}}(c, \text{centre})}{\text{scale}},\qquad d \le r$$

so the centre receives `0.90`, the four cells at `d=1` receive `0.60`, the eight
at `d=2` receive `0.30`, and the four **corners of the 5×5 box are left at zero**
— the non-zero footprint is a 13-cell Manhattan diamond inscribed in the
declared 5×5 window. Kernels at board edges are **clipped**, never wrapped and
never redistributed; a trace near a wall is genuinely weaker, which is a
physical claim the model makes deliberately.

**Documented discrepancy — geometric vs. subtractive decay.** The reference
simulator's description of ρ implies *subtractive linear* decay, i.e.
`τ − ρ` per turn, under which a 0.9 deposit vanishes in ten turns. This project
implements *geometric* decay, `(1 − ρ)·τ`, under which the same deposit retains
`0.9 × 0.9¹⁰ = 0.314` after ten turns, falls below `0.01` only at turn 43, and
is retired at turn 268 when the field's 12-digit rounding finally zeroes it. On
a 35-move match a trace therefore **fades but never expires**, and nothing
clears the field on a schedule. This is a real modelling divergence from the
reference, not a rounding artifact, and it is recorded here, in the module
docstring, in the GUI docstring, and in README §7 so no reader mistakes it for a
bug. Read ρ = 0.10 as "loses a tenth of *what remains* each turn".

**Consequence for the GUI.** The field is a *concentration*, not a normalised
probability: overlapping kernels can exceed 1.0 (observed peak `2.41` on a real
match), so the heatmap clamps its shading rather than claiming a probability it
does not compute.

### 4.2 Cop Belief & Action Selection (`strategy/qvalues.py`, `strategy/belief.py`)

**Opponent-position belief** comes from a hybrid source, resolved in
`AgentPolicy.hybrid_opponent_cell` (D2): use the opponent's *resolved* position
when one was supplied for this turn, and otherwise fall back to
`PheromoneField.strongest()` — the highest-concentration cell, i.e. the field's
maximum-likelihood estimate of where the opponent is. The hybrid is resolved
inside the policy, not by the caller, so no call site can silently skip the
fallback.

**Which branch runs, and where — the honest split.** These are two different
regimes and the document does not pretend otherwise:

| Regime | What supplies the opponent cell | Field's role |
|--------|--------------------------------|--------------|
| Offline training (`scripts/tournament_loop.py`) | Resolved cell from turn 1 on; **withheld on turn 0** | Supplies the turn-0 belief, carrying memory across the 2000-game series (§4.1) |
| Live P2P match (`scripts/match_loop.py` → `PeerClient.prepare`) | Signed, revealed coordinate **every turn**, starting from the configured start cells | Never consulted; never deposited into |
| Replay / GUI (`scripts/render_replay.py`) | — | Rebuilt from the signed log to render the heatmap |

**Why live play coordinates directly rather than through the field.** A league
match is a zero-trust, latency-bounded exchange: the commit-reveal protocol
(§3) already delivers each peer a *signed, mutually verified* coordinate every
turn, and both peers' independent engines are compared against it (§2). Routing
that through a concentration field would substitute an estimate for a fact that
has already been cryptographically established, and would widen the effective
state space at exactly the moment the match is on a clock. Direct coordination
over FastMCP therefore drives live play, and the field earns its keep offline
and in the replay tooling. This is a deliberate trade, and the cost is stated
in §10.4: the shipped policy has never had to act on a purely inferred
position during a graded match.

**Why the field, rather than a Bayesian posterior, where belief IS used.** A
posterior over opponent position is a distribution across all 49 cells;
carrying it into a tabular Q-learner means either discretising it into the
state key — which multiplies the state space by the number of representable
distributions and destroys any hope of visiting each state often enough to
converge — or maintaining it alongside the table as a second, separately-tuned
model. The concentration field already *is* a recursively-updated, decaying
estimate of where the opponent has been, and `strongest()` collapses it to the
single cell the Q-learner needs. One scalar per cell, one maximum, one relative
displacement in the state key: the state space stays small enough to converge
over 2000 training games, which a posterior-conditioned key would not.

**Action selection** is tabular Q-learning, not a hand-written pursuit
heuristic. The update rule is exact:

$$Q(s,a) \leftarrow Q(s,a) + \alpha\bigl(r + \gamma \max_{a'} Q(s',a') - Q(s,a)\bigr)$$

with the bootstrap term omitted on terminal transitions. The state key is
`(relative_opponent, barrier_mask)`:

- `relative_opponent` is the opponent cell **minus own cell** — a translation-
  invariant displacement vector, which is what lets one learned entry generalise
  across the board. It is `None` when no belief exists.
- `barrier_mask` is a 4-bit adjacency mask over `N, S, W, E`; **off-board
  neighbours count as blocked**, so walls and barriers are one concept to the
  learner.
- `move_count` is deliberately **excluded**: including it would make every turn a
  distinct state and destroy generalisation entirely.

Selection is ε-greedy (`exploration_rate = 0.1`, decayed by `0.999` per episode
to a floor of `0.01`); `match_exploration_rate = 0.0` so competitive play is
purely greedy. Ties resolve in `move_set` order, which keeps `best_action`
deterministic — except on a state where *every* action is still exactly `0.0`,
which carries no preference to break. Those defer to the greedy Manhattan
tie-break in `strategy/fallback.py` (§10.10): the cop takes the legal step that
minimises the distance to `relative_opponent`, the thief the one that maximises
it, still deterministically and still in `move_set` order on a tie. One learned
value on the state, positive or negative, suppresses it entirely. The table
persists to `data/q_table_<role>.json` behind
`STATE_LAYOUT_VERSION = 1`; a version mismatch raises rather than silently
loading incompatible keys.

**Reward signal — terminal-dominated, with two shaping terms.** The outcome
reward comes from the shared `scoring` block — capture: cop `20`, thief `5`;
survival: cop `5`, thief `10`; tie `2`; technical loss `0` — so both peers
optimise against the same published payoff matrix, and it is paid on the
terminating transition only. Terminal-*only* rewards, the original PLAN_05
ruling, turned out to be degenerate: bumping the north wall and advancing
toward the opponent were both worth exactly zero, so nothing in the signal
distinguished a pursuing policy from one grinding into a boundary, and a
"always N" policy survived training intact. Two configured terms in each peer's
private `[strategy]` block close that gap, and only those two:

| Term | Value | Fires when |
|------|-------|-----------|
| `invalid_move_penalty` | `-1.0` | a non-`STAY` move leaves the agent in the cell it started from — a barrier or the board edge refused it |
| `step_cost` | `-0.01` | every turn that does not end in a capture, so the shortest pursuit is the most valuable one |

Both stay orders of magnitude below the payoff matrix — a full 35-move match of
`step_cost` is `-0.35` against a capture worth `20` — so the terminal signal
still dominates and the reward is shaping, not a rewritten payoff. A per-turn
*survival* reward is still refused for PLAN_05's original reason: it would pay
an agent for merely existing. Distance shaping is still refused too; neither
term looks at the opponent. The reported GAME SCORE is the engine payoff alone,
so shaping cannot leak into results
(`tests/scripts/test_shaped_rewards.py`, `test_shaping_terms.py`).

**Honesty belief** (`BeliefTracker`) is a *separate* axis and must not be
confused with position belief. It scores each revealed `intent` against the move
actually played: `honest`, `dishonest`, or `unscorable`. An intent naming no
direction is *absent* evidence, not negative evidence, and never moves the
honesty rate. Matching is word-boundary aware — full direction words match as
prefixes (so "northern" names north) while single letters must stand alone, which
stops incidental text such as `SNOW` or `NEWS` from naming a direction. The rate
is a frequentist ratio `honest / (honest + dishonest)` over scorable
observations, falling back to the configured `honesty_prior = 0.5` when there is
no evidence. The thief's policy inverts its stated intent by design
(`AgentPolicy.intent_for_move`), so the tracker has a real signal to detect;
intents are truncated to `hint_max_words = 15`.

**Naming note.** The system uses no Bayesian posterior update and no
Manhattan-distance target-routing heuristic. Manhattan distance appears as the
*kernel falloff metric* in §4.1; belief is a decaying concentration field
(rationale above), and routing is learned, not computed. This paragraph exists
so the specification is not read as promising machinery that the implementation
does not contain.

### 4.3 Barrier Initialisation (`engine/barriers.py`)

`max_barriers: 14` was configured from Phase 0 but never populated: every play
path built a bare `Board`, so `place_barrier` had no caller outside its own
tests and the state key's `barrier_mask` only ever encoded board edges. §10.10
records the consequence — on a bare 7x7 grid under simultaneous moves a single
pursuer cannot corner a perfectly evading thief, measured at **0.0%** capture
for every policy. Barriers are what create the cul-de-sacs that make cornering
possible, so activating them is a strategy change, not a cosmetic one.

**The layout is derived, never stored.** `barrier_layout(config)` returns a
`frozenset` of cells computed from `barrier_seed` and `max_barriers` alone.
Both peers load the same shared `game.json`, so both derive the identical
board without exchanging it — the layout needs no wire message and cannot
drift between the two mirrored engines (§2). A layout that had to be
transmitted would be one more thing a hostile peer could lie about.

**Two invariants, both enforced at generation:**

* **Start cells are never barriered.** `cop_start` and `thief_start` are
  excluded before sampling, so no agent begins inside a wall.
* **The free space stays connected**, and both starts are in it. A random
  scatter of 14 cells over 47 can wall a region off entirely, which would make
  capture arbitrary rather than skilful. The generator resamples under a
  deterministic counter until connectivity holds, so the retry costs
  reproducibility nothing.

**`barrier_seed: null` means a bare board**, which is what makes this change
backwards compatible. One key controls both activation and layout; there is no
separate boolean to fall out of step with it.

**Replay compatibility.** The flagship log under `logs/aviayeli/` was played
before this phase, on a bare board. `build_log` now records the layout under
`barriers`, and `check_replay` reconstructs the board from that field —
falling back to a bare board when the key is absent, which is exactly the
shipped log's case. `scripts.replay_match` therefore still returns
`Verified OK` on signed evidence recorded under the old regime, without
re-sealing an artifact to match new code (§10.10, *Provenance*).

## 5. Step-0 Declaration & Hardware Scan (`mcp_server/declaration.py`)

At turn 0 each peer publishes a computational-fairness declaration so neither
side can later claim it was outgunned. The payload is deterministic and
`declaration_<game_id>.json` is written alongside the match artifacts:

| Field | Source | Failure posture |
|-------|--------|-----------------|
| `group_name`, `members`, `repos`, `mcp_servers` | `config/declaration.json` | **Loud** — missing config raises |
| `token_budget`, `num_games`                      | `config/game.json::network_and_league` | **Loud** |
| `hardware.os`                                    | `platform.platform()` | sentinel `unknown` |
| `hardware.cpu`                                   | `platform.processor()`, falling back to `/proc/cpuinfo` `model name` | sentinel `unknown` |
| `hardware.ram`                                   | `SC_PAGE_SIZE × SC_PHYS_PAGES`, reported in GB | sentinel `unknown` |
| `hardware.gpu_vram`                              | `nvidia-smi --query-gpu=memory.total` | sentinel `none` |
| `github_commit_hash` / `github_commit`           | `git rev-parse HEAD` | sentinel `unknown` |
| `timezone`                                       | local `tzname()` | sentinel `unknown` |

The two postures are deliberate and opposite. **Declared** fields fail loudly:
emitting `"unknown"` into an artifact submitted for grading is worse than
crashing. **Probed** fields degrade to a sentinel: host inspection varies by OS
and must never prevent an artifact from existing.

**Limitation, stated plainly.** The declaration is an **unsigned, unenforced**
record of what a peer *claims* to be running. It is not covered by the Ed25519
submission signature of §3, and nothing in the system can detect a peer running
a different commit than the hash it declared. It is provenance and good faith,
not proof of fairness. Extending the Ed25519 signature to cover the declaration
payload is the obvious hardening and is listed in §10.

## 6. Observability & Verification

### 6.1 Replay Verifier (`scripts/replay_match.py`, `scripts/log_checks.py`, `scripts/log_shape.py`)

An independent third party — the grader — must be able to take a log file and
the two public keys and confirm the match happened as recorded, with no access
to either peer. `Verified OK` is printed **only** when all five checks pass:

1. **Structure** — the log has the shape a match record must have.
2. **Turn indices** — contiguous and ascending.
3. **Commitments** — every digest re-derives from its revealed tuple.
4. **Signatures** — every signature re-verifies against that peer's public key
   *for the turn it claims*.
5. **Replay** — replaying the logged moves reproduces **every recorded turn
   result**, and the number of logged turns equals the number the replay reached.

Anything less prints `TAMPERED!` and exits non-zero. Checks 3–5 encode audit
findings that are worth preserving as design rationale: an earlier version
compared only the *final* state, so a wholly fabricated match middle certified
clean (V1); indices (V2) and turn counts (V3) went unchecked, so turns could be
padded on after termination where `step()` is a no-op; and hostile field types
crashed the verifier, letting an attacker trade a verdict for a traceback that
CI might read as infrastructure failure (V4). Every check therefore **appends to
a shared failures list rather than raising**, so one bad field cannot mask the
rest of the report, and `verify_log` wraps everything in a blanket `except` —
a verifier exists to *answer*.

Cross-peer agreement is deliberately **not** re-checked here: it is enforced at
match time by `play_match`, where both engines are compared every turn.

### 6.2 Live GUIs — Tkinter and CLI (`gui/`, `scripts/render_replay.py`)

Two rendering paths, deliberately: a windowed one for demonstration and a
terminal one for headless machines and CI, both driven by the *same* frame
reconstruction so they cannot disagree about what a log contains.

**CLI.** `scripts.replay_match --render` draws each turn on an ASCII board
before printing the verdict — additive, off by default, and it changes no
verdict. `--render-delay` paces it and `--step` waits for Enter between turns.
`scripts/heatmap.py` prints the belief field the same way. Colour is suppressed
when the stream is not a TTY or when `NO_COLOR` is set, so piped and
pytest-captured output stays byte-clean and escape sequences never leak into an
assertion.

**Tkinter.** Two windowed surfaces share one canvas and one palette:

- **Replay Viewer** (`gui/replay.py`) — step-by-step, with a green `Verified OK`
  badge on a clean log and a red `TAMPERED!` banner on an altered one. The badge
  is driven by the *same* `verify_log` the headless CLI uses, so the window
  cannot disagree with `scripts.replay_match`. Frames are reconstructed from the
  logged **moves**, not the recorded positions, so a forged log is drawn as it
  truly replays rather than as it claims to look.
- **Live Heatmap** (`gui/live_heatmap.py`) — auto-advancing (`700 ms`), shading
  each cell in proportion to its pheromone concentration, so the thief's trail
  visibly builds and fades. The rendered board is the full 7×7; the 5×5 figure
  is the scent *kernel* stamped onto it, not the display size.

## 7. Automated Reporting

### 7.1 Match artifacts (`scripts/match_log.py`)

Four files per game, written under `logs/<group_id>/` with deterministic JSON
(`indent=2`, `sort_keys=True`, trailing newline) so repeated runs are
byte-identical:

| Artifact | Contents |
|----------|----------|
| `declaration_<game_id>.json` | §5 payload, schema fixed by `PRD_03` FR6 |
| `config_<game_id>_g<NN>.json` | Snapshot of the shared contract the match actually ran under, stamped with `game_uid` |
| `log_<game_id>_g<NN>.json` | Per turn: both peers' `h_commit`, `signature`, `state`, `move`, `intent`, `nonce`, plus the outcome |
| `result_<game_id>.json` | Series summary: commit hash, repos, `mutual_agreement`, per-game turns / capture / terminal reason / final positions |

The log is written to be **sufficient for replay on its own** — a verifier needs
nothing but the file and the peers' public keys. The config is *copied* rather
than referenced so the artifact records what actually ran, and all four are
stamped with the same identity so they tie together.

`mutual_agreement.confirmed` is not a courtesy flag: `play_match` compared both
peers' independent engines on every turn and would have raised
`DivergenceError`, so a history that reached the writer *is* the evidence.

**Schema caveat.** Appendix F of `police_thief_p2p.pdf` is not in this
repository. Only the four *filenames* come from the specification; the field
layout of the config/log/result payloads is this project's own design and must
be reconciled with the real appendix before final submission.
`declaration_<game_id>.json` is the exception — its schema is fixed by `PRD_03` FR6.

### 7.2 Gmail API reporting (`reporting/`, Rulebook 34 / §9.3.3)

Three modules, split by concern: `email_sender.py` holds **policy**,
`mime_report.py` holds **message construction**, `gmail_transport.py` holds
**delivery**.

- **The result is an attachment, never body text.** The message is
  `multipart/mixed` with exactly one `application/json` part, named
  `result_<game_uid>.json` to match the on-disk artifact. This is a submission
  requirement, and it is also the only form that survives the trip: a body is
  reflowed, quoted and line-wrapped by every client between here and the grader,
  whereas a base64 `application/json` part arrives byte-identical. The body is a
  summary and is kept free of braces so the "no plaintext report" rule is
  *mechanically* checkable (`tests/unit/test_email_attachment.py`).
- **Mutual agreement is a precondition.** `send_game_report` refuses to report
  a result whose `mutual_agreement.confirmed` is not literally `True`. Reporting
  an unagreed result would launder a divergence into a submission.
- **A missing credential must never break CI.** Modes are `auto` (send if
  credentials exist, otherwise draft), `draft` (never contact Google), and
  `send` (require real delivery and report failure rather than quietly
  drafting). On fallback, `logs/email_draft_<uid>.txt` records the summary *and*
  the decoded attachment, so there is always a file on disk stating exactly what
  would have gone out — a draft that held only the body would record that a send
  was attempted while losing the result it was attempting to send.

**Recipient resolution — two sources, and the config wins.**
`email_sender.DEFAULT_RECIPIENT` is the course address
`rmisegal+uoh26finalgame@gmail.com`, and it is the value used whenever
`send_game_report` is called without an explicit recipient (pinned by
`tests/unit/test_email_sender.py`). The live match path does **not** take that
default: `scripts/match_report.report_by_email` reads `[email]` from
`config/<role>/game.toml` and passes `recipient=` explicitly, so the configured
value overrides the constant. Both peers' `[email]` blocks are identical and the
`police` block is the one read.

**Shipped setting.** Both files now configure the course address
`rmisegal+uoh26finalgame@gmail.com` with `mode = "auto"`, and
`tests/unit/test_shipped_email_config.py` holds them there. `auto` is the only
mode that survives a grader's machine: `send` requires a real delivery and
reports failure rather than drafting, while `draft` never attempts one. Under
`auto` the reporter sends when credentials exist and otherwise writes the local
draft artifact and returns success, so a missing `token.json` degrades to
evidence on disk rather than a crash.

Delivery uses the Gmail API with the OAuth token at `token.json`.

## 8. Data Flow (per turn, distributed)

```
each peer: tools.get_observation(role)              [WAITING_FOR_OPPONENT]
  → PeerClient.prepare(turn, own_pos, opponent_pos, board)   [COMPUTING_MOVE]
      → AgentPolicy.state_key()  → hybrid: resolved pos, else pheromones.strongest()
      → qvalues.select_action()  → intent_for_move() → truncate to hint_max_words
      → crypto.commit(state, move, intent) → (h_commit, nonce)
      → identity.sign(key, role, turn, h_commit)
  → broadcast submit_commitment(...) to BOTH peers            [COMMITTING]
      → SubmissionGate: verify_signature → CommitmentBook.commit
      → refuse reveal until len(commitments) == 2             [AWAITING_REVEAL]
  → broadcast reveal_move(...) to BOTH peers                  [VERIFYING]
      → CommitmentBook.reveal → crypto.verify(state, move, intent, nonce, h_commit)
      → MatchState.submit under asyncio.Lock
          → both slots filled → GameEpisode.step(cop_action, thief_action)
              → resolver.resolve_turn()  [FR5 steps 1–3]
          → buffer cleared, history appended, termination checked
  → match_loop.divergence(): compare BOTH peers' results, field by field
      → mismatch → DivergenceError (abort)                    [→ WAITING_FOR_OPPONENT]
  → AgentPolicy.observe_opponent(): belief.record() + pheromones.advance()
```

## 9. Determinism Strategy (FR7)

- The engine uses no randomness, wall-clock time, or other non-deterministic
  source. All clocks in the protocol layer (`MatchState`, `CommitmentBook`,
  `SubmissionGate`) are **injectable**, so timeout behaviour is testable without
  sleeping.
- Policy randomness is confined to explicitly-seeded `Random` instances derived
  from one master seed in `run_local_mcp_match.build_clients`, and the seed is
  printed with every match summary so any match reproduces exactly.
- All state mutation happens inside `GameEpisode.step()`; `resolver.py` and
  `player.py` are pure functions over their inputs.
- Artifacts are written with sorted keys and fixed indentation, so a
  reproduction is byte-comparable, not merely semantically equal.
- `GameEpisode.history` records every `(cop_action, thief_action, TurnResult)`,
  which is sufficient to reconstruct an episode via `replay()` — the property the
  verifier's check 5 depends on.

## 10. Known Limitations & Specification Deltas

Every limitation below is measured, tested, and reproducible. Items 4 and 10
record deliberate architectural trades; item 7 is the only untested dependency.

Item numbers are stable identifiers and are referenced from source, tests and
the README as `§10.N`; the two groupings below reorder nothing.

### Deliberate Architectural Trade-offs

Decisions taken with the alternative understood, each stating what it costs.

-   **§10.2 — Commit payload has no field delimiters** (§3), because Rulebook 5.3
   specifies positional concatenation. Interop-correct, cryptographically
   weaker than a delimited encoding.
-   **§10.3 — Scent decay is geometric, the reference simulator's is subtractive**
   (§4.1). Traces fade but do not expire within a 35-move match.
-   **§10.4 — The scent trail is an offline and observability substrate, not the live
   belief input** (§4.1, §4.2). Live P2P play uses direct coordination over
   FastMCP: the commit-reveal protocol delivers a signed, mutually verified
   opponent coordinate every turn, so `hybrid_opponent_cell` never reaches its
   fallback and a live peer's field is never deposited into. The field does
   real work in two other places — it supplies the turn-0 belief in every
   offline training episode, carrying decaying memory across the 2000-game
   series, and it is rebuilt from the signed log to drive the replay heatmaps.
   This is a **chosen trade**: substituting an estimate for a coordinate the
   protocol has already established cryptographically would add state-space
   width and latency to a clocked match and buy nothing. The cost is real and
   is recorded here rather than argued away — the shipped policy has never had
   to act on a purely inferred position under match conditions, so the
   fallback branch is exercised by training and tests, not by graded play.
   Relatedly, there is **no Bayesian posterior and no Manhattan
   target-routing**: where belief *is* consulted it is the concentration field
   collapsed to `strongest()`, because conditioning a tabular state key on a
   49-cell distribution would explode the state space beyond what 2000 games
   can visit. The cop therefore reasons about one most-likely cell and cannot
   express uncertainty between two equally-plausible hiding places.
-   **§10.6 — Peer traffic is authenticated but not encrypted** (§3). Signatures prevent
   forgery and replay; they do not provide confidentiality on the wire.
-   **§10.8 — A clean checkout cannot both verify the shipped log and play live**
   (§3, `mcp_server/keygen.py`). The tracked `.pub` files are the keys the
   flagship log was signed under; `signing_key.pem` is gitignored. On an
   untouched clone `ensure_keys` therefore refuses to republish public halves
   it would otherwise overwrite, so `scripts.replay_match` still returns
   `Verified OK` — at the price that the freshly generated private key does
   not match the published public one, and live play is signature-rejected
   until the operator restores the real `.pem` or deletes the shipped `.pub`
   files. Verifiability of shipped evidence is treated as outranking live play
   on a clone; the refusal is announced on stdout rather than inferred.
-   **§10.10 — Off-manifold generalisation and heuristic baselines** (§4.2,
    `strategy/fallback.py`). Self-play converges to a 99.85% series capture
    rate, but that is convergence *against one thief on one trajectory
    manifold*. Probing the shipped cop table from 400 uniformly random,
    distinct start pairs (seed `20260817`, the barriered board of §4.3,
    epsilon = 0, the opponent cell revealed every turn) finds
    **37.2% of decision states wholly unvisited** — every action reading
    `initial_q_value`. The figure has moved with every regime and all of them
    are recorded: 58.2% on the bare grid, 66.3% once barriers were placed
    (more reachable states, same budget), 36.3% once self-play became
    contested, and 40.5% now that training draws from an opponent pool across
    varied layouts — a wider distribution to cover, over 10,000 episodes
    instead of 2,000, and 37.2% once the exploration schedule was retuned for
    that longer run (the previous decay floored epsilon at episode 2,302,
    leaving 77% of training at minimum exploration).

    Before this phase a wholly flat state fell through `best_action`'s
    move-set tie order to `move_set[0]` — a literal "always N", with match-time
    epsilon = 0 leaving no exploration to escape it. The distance rule that
    replaced it is arithmetic on the state key alone: that key already carries
    the opponent's RELATIVE cell, so each candidate step's resulting distance
    needs no new observation and no wider state space, and the barrier mask in
    the same key keeps the choice legal. The cop minimises the distance, the
    thief maximises it, STAY is always a legal candidate.

    **Which strategy leads is per-peer configuration** (`policy_mode` in each
    private `game.toml`), not a role check in Python:

    * `qtable_primary` — the table decides; the distance rule runs only where
      every action on the state is exactly `0.0`. The **thief** ships this.
    * `manhattan_primary` — the distance rule narrows the legal moves to the
      distance-optimal set, and the table ranks what is left. A learned value
      can never escape that set, however large. The **cop** ships this.

    Cop capture rate / mean turns-to-capture over the 400-start probe, on
    the barriered board (§4.3), against the Phase 11 evader:

    | Cop policy | vs. random thief | vs. greedy evader | vs. trained thief |
    | :--- | :---: | :---: | :---: |
    | `qtable-only` — no distance rule at all | 93.0% / 7.53 | 19.0% / 13.11 | 23.2% / 19.20 |
    | `qtable-primary` — distance only on flat states | 99.2% / 7.22 | 20.2% / 13.00 | 26.8% / 20.16 |
    | `manhattan-primary` — **shipped**, table breaks ties | 100.0% / 6.11 | 41.5% / 16.01 | 36.8% / 20.83 |
    | `heuristic` — same rule, EMPTY table, ties by move-set order | 99.8% / 6.19 | 30.2% / 17.92 | 22.0% / 15.45 |

    Reproduce with `PYTHONPATH=src python -m scripts.benchmark_offmanifold`;
    the sample size, seed and opponent set are `config/benchmark.json`, not
    literals in source. Every figure in this section is re-derived from a real
    run by `tests/scripts/test_benchmark_plan_claims.py`, so retraining the
    tables fails the suite rather than silently stranding the prose — the
    posture `test_readme_consistency.py` already takes toward the README.

    Five readings, none of them flattering by omission:

    * **Learning is now an ASSET against an unseen opponent, and this
      reverses the previous finding entirely.** Measured against a heuristic
      pursuer it never trained against, the evader survives **90.0%** carrying
      its trained table against **69.8%** carrying an empty one. Under
      self-play the same measurement read **2.2%** against 69.8% — learning
      was a 30x liability. The cop shows the same reversal: against our own
      trained evader the shipped policy scores 36.8% where an empty table
      scores 22.0%, having previously LOST that comparison 53.5% to 92.0%.
      Opponent diversity was the whole of the fix.
    * **The learned table now pays off against EVERY opponent in the set, and
      that is new.** Until the exploration schedule was retuned it was level
      with an empty table against a greedy evader (29.8% against 30.2%) and
      only helped against a strong one. Retuning `epsilon_decay_factor` for
      the 10,000-episode run — it had been calibrated for a 2,000-game series
      and floored at episode 2,302 — lifted the greedy column to **41.5%
      against 30.2%**. The tie-break is no longer decoration against simple
      opponents.
    * **Both roles now ship the same priority, and the split that made them
      differ is no longer needed.** Phase 11 had to separate training from
      match priority because a cop trained under `qtable_primary` against a
      strong evader never won and learned nothing (0.05% capture). Trained
      against a pool, distance-first is best in both phases for both peers.
      `match_policy_mode` is retained and still tested; it simply does not
      need to differ today.
    * **Retuning exploration TRADED evader strength for cop strength, and the
      trade was taken on league arithmetic rather than on either number.** The
      evader fell from 90.0% survival against a heuristic pursuer to **78.0%**
      while the cop rose from 29.8% to 41.5% against a greedy evader. Because
      `capture_cop` pays 20 and `survival_thief` pays 10, the expected return
      per role-pair rises from 14.96 to **16.10 points**: the cop's +11.7 is
      worth double the evader's -12.0. The evader remains the stronger agent
      in absolute terms, and it is still the one worth fewer points.
    * **The learned edge DOES NOT TRANSFER to an unseen barrier layout, and
      this was found by a multi-model debate rather than by any of the five
      single-model sittings.** `barrier_mask` is part of the state key, so a
      layout the table never trained on invalidates the learned states
      directly. Measured over 8 layouts each:

      | Layouts | trained table | EMPTY table | delta |
      | :--- | :---: | :---: | :---: |
      | seen in training (seeds 0-19) | 60.6% | 50.7% | **+9.9** |
      | never trained on (seeds 1000+) | 55.1% | 57.4% | **-2.2** |

      So the +11.3 point gap the shipped layout shows is a favourable draw,
      not a transferable gain: the DISTANCE RULE generalises and the learned
      increment on top of it does not. The -2.2 is **not** evidence that the
      table actively hurts — a multi-model panel corrected that reading, and
      the correction stands: the gap sits inside sampling error, so on an
      unseen board the learned values are *inert*, not corrupting. They cannot
      be corrupting, because `barrier_mask` in the key means an unseen layout
      misses every entry and the composite falls through to the distance rule
      by construction. The honest claim is "no measurable advantage off the
      trained layouts", not "worse". The first version of this measurement
      was itself confounded — it probed seeds 0-19, which are inside the
      64-layout training pool — and is recorded here because the corrected
      result is the one that matters. Pinned by
      `tests/scripts/test_layout_transfer.py`. The remedy is layout diversity
      wider than the state key can memorise, or a function approximator;
      neither is implemented.
    * **Generalisation was bought, not free.** The off-manifold rate ROSE to
      40.5%, both tables roughly doubled in size, and the shaping penalties had
      to be strengthened (step cost -0.1/-0.05, refused move -1.5) to teach
      spatial awareness across varied layouts. What the pool removed was
      overfitting to one adversary; it did not make the state space smaller.
      The barrier result underneath all of this is unchanged and still holds:
      **On a bare board every cop policy scores 0.0%** against a greedy
      evader, and across 20 independent layouts every one beats bare (mean
      37.1%, range 10.0-59.0%). Training now draws from 64 of those layouts
      rather than the single shipped one.

    **Provenance of the shipped evidence.** The flagship artifacts under
    `logs/aviayeli/` — the signed match log, its `result`, and
    `declaration_aviayeli.json` — were recorded at commit `1d9d40e`, which
    predates both `strategy/fallback.py` and this priority swap. That is stated
    rather than hidden, and the artifacts are deliberately **not** regenerated:
    they are signed evidence of a match that was actually played, and
    re-sealing them to carry a newer commit hash would trade a genuine record
    for a cosmetic one.

    **The trajectory they record is NO LONGER what today's policy produces**,
    and this section once claimed the opposite. The log records a capture on
    turn 3 at `(1, 2)`. From the same published starts the shipped cop now
    does not capture at all: the episode runs to the 35-move limit, because
    Phase 11 gave the evader the distance rule and our own thief escapes our
    own cop. The claim was true when written, was not pinned by any test, and
    went stale silently the moment the policies moved —
    `tests/unit/test_flagship_provenance.py` now re-derives the relationship on
    every run so it cannot drift again. (The sentence also cited
    `tests/mcp_server/test_qvalues_fallback.py` as support; that file tests the
    fallback rule generically and never asserted this trajectory, so the
    citation was overstated independently of Phase 9.)

    None of that invalidates the artifacts. They remain a signed, verifiable
    record of a match that was really played, and `scripts.replay_match` still
    returns `Verified OK` on them, because a replay is checked against the
    board the log records (§4.3) rather than today's configuration. What they
    demonstrate is the PROTOCOL and the verifier. What they do NOT demonstrate
    is the current policy, nor the off-manifold behaviour this section
    measures — both are exercised by the benchmark and the suite.

    The external audit's own figures — 47.2% / 3.69 turns for the baseline and
    93.5% / 6.04 for the heuristic — are recorded here as the prompt for this
    work, not as this repository's evidence: its protocol is unpublished. They
    were taken against the BARE grid, and reproduced closely under that regime
    (heuristic mean turns 6.04 against 6.10 measured; off-manifold rate 58.9%
    against 58.2%). They are not comparable to the barriered figures above and
    are retained only as the historical prompt.

    What none of this buys is generalisation. The remedy is a legality- and
    distance-aware ordering, not learning. The real fix remains opponent
    diversity in training or a function approximator — a training phase in its
    own right, as recorded under the self-play limitation above.

### Unimplemented / Future Scope

Work not done. Nothing here is argued to be unnecessary; each names what would
close it.

-   **§10.1 — The Step-0 declaration is unsigned and unenforced** (§5). It records a
   claim, not a proof. Covering it with the existing Ed25519 signature is the
   natural hardening.
-   **§10.5 — Artifact field layout is this project's own design** (§7.1), pending
   reconciliation with Appendix F.
-   **§10.7 — League play against the opposing group has not been run.** The system is
   validated by two *local* peers over a real streamable-HTTP transport with
   commit-reveal and signatures fully in force, which removes the external
   dependency but does not substitute for a cross-group match.
-   **§10.11 — Unimplemented contract obligations, and the pattern behind
    them.** Three keys of the contract stamped
    `agreed_between: ["aviayeli", "groupb"]` were found ASSUMED rather than
    read, each long after it shipped: `max_barriers` (configured Phase 0,
    populated by nothing until Phase 9, and measured at a 0.0% capture rate
    against a greedy evader), `barrier_seed` (added as REQUIRED, which made
    the agreed schema unloadable — a technical loss before turn 0), and
    `axis_origin_corner` (stated in an `actions.py` docstring and never
    compared against the negotiated value, so a peer on `bottomleft` would
    have mirrored every move and produced a plausible WRONG game rather than
    an error). The `rate_limiter_gatekeeper` block — five agreed tunables —
    was likewise declared and unread, which is a forfeit path rather than a
    discourtesy: a peer that enforces the limit drops us, and `http_peer`
    turns a dropped call into `TechnicalLossError`.

    All four are now implemented (§2, §4.3, `mcp_server/rate_limiter.py`), but
    the finding is the PATTERN and not any one instance: each was caught by a
    human rereading months apart, never by a check.
    `tests/mcp_server/test_contract_coverage.py` now fails the suite when a
    contract key is neither read in `src/` nor whitelisted with the reason it
    never will be. What remains deliberately unimplemented is listed there
    rather than here, and is confined to league SCORING the organiser awards
    (`diversity_reward`, `min_games_to_pass`, `max_games_per_team`) plus
    genuinely inert fields (`map_area`, `num_agents`, `schema_version`,
    `agreed_between`). Nothing behavioural is now declared and unread.

-   **§10.9 — A stalled peer ends the match, it does not end the process** (§3). Every
   wire call is fenced by the published `watchdog_timeout_sec` and raises
   `TechnicalLossError` on expiry (`mcp_server/http_peer.py`). What is *not*
   implemented is an automatic award of the technical win to the surviving
   peer: the error is raised to the caller, which decides. The forfeit path
   that the server already runs on its own commitment deadlines (§3) is
   unaffected.

## 11. Test Strategy

Every module was built test-first per `CLAUDE.md`; `docs/TODO.md` records the
sequencing and the evidence. The suite mirrors `src/` and currently stands at
**914 passing tests**. The load-bearing cases, by layer:

- **Engine** — the six FR5 scenarios (both unobstructed, bounds-blocked,
  barrier-blocked, same-cell capture, swap capture, adjacent near-miss), plus
  the case where a move first resolves to `STAY` and *then* collides, proving
  capture is evaluated on resolved rather than intended positions.
- **Protocol** — reveal-before-commit refusal, replayed and cross-turn
  signatures, `broken_commitment`, stale/advancing turns, double submission, and
  concurrent submission proving exactly one `step()` per turn under the lock.
- **Strategy** — exact kernel values by Manhattan distance, the `max(0, …)`
  clamp under signed deltas, edge clipping, exact TD-update arithmetic, state-key
  generalisation, and Q-table round-tripping under the layout version.
- **Verification** — a tampered middle turn, a padded turn count, a
  non-contiguous index, a hostile field type, and a valid log, each asserted
  against the exact verdict.
- **Reporting** — multipart shape, single JSON part, filename, payload
  round-trip, brace-free body, the mutual-agreement refusal, and the draft
  fallback containing the whole report.
- **Consistency** — `test_declaration_agrees_with_transport` (ports),
  `test_readme_consistency` (self-checked figures), and the 150-line audit over
  `git ls-files '*.py'`.
