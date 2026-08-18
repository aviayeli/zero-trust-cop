# TODO — Living Delivery Checklist (Phases 0–5)

Executes [`docs/PLAN.md`](PLAN.md) under strict TDD per `CLAUDE.md`: for every
module, its test file is written and confirmed **failing** immediately before its
implementation file is written, and confirmed **passing** immediately after. No
task here writes implementation code before its paired test task.

This file is the top-level, cross-phase checklist. The per-phase TODOs
(`TODO_02_MCP_Server.md`, `TODO_03_Security.md`, `TODO_05.md`, `TODO_06.md`,
`TODO_07.md`) retain the full assertion-by-assertion detail for their phases;
items here are the milestone rollups, each carrying the evidence that closed it.

**Gate status:** `pytest -q` → **846 passed**. Every `src/**/*.py` is ≤150 lines
(longest: `scripts/render_replay.py`, 148). `scripts.replay_match
logs/aviayeli/log_aviayeli_g01.json` → `Verified OK`.

---

## Phase 0 — Deterministic Game Engine

Order follows the dependency chain: `errors.py` → `config.py` → `actions.py` →
`board.py` → `player.py` → `resolver.py` → `game_loop.py`, then cross-module
integration and replay.

### 0.0 Scaffolding

- [x] Create `src/engine/__init__.py` (empty package marker).
- [x] Create `tests/engine/__init__.py`. *(Later removed: a `tests/engine`
      package collides with the `src/engine` package name under pytest import;
      resolved via `--import-mode=importlib` and no `__init__.py` under `tests/`.)*
- [x] Add the `pyproject.toml` pytest configuration so `tests/` is discoverable.
- [x] Confirm the runner executes with zero collected tests and no errors.

### 0.1 `errors.py` (leaf)

- [x] **Test first**: `tests/engine/test_errors.py` — `InvalidActionError`,
      `BarrierLimitError` and `IllegalBarrierPlacementError` exist, subclass
      `Exception`, and each raises/catches with a custom message.
- [x] Confirm the tests **fail** (module does not exist).
- [x] **Implement** `src/engine/errors.py` — exactly those classes, nothing else.
- [x] Confirm they **pass** (6 passed). Under the limit at 19 lines.

### 0.2 `config.py` (leaf)

- [x] **Test first**: `tests/engine/test_config.py` — `load_config` returns a
      `GameConfig` with `grid_size == 7`, `cop_start == [0,0]`,
      `thief_start == [3,3]`, `move_set == ["N","S","E","W","STAY"]`,
      `max_barriers == 14`, `max_moves == 35`, `survival_threshold == 35`, and
      raises a clear error — never a silent default — on a missing file or key.
- [x] Confirm the tests **fail**.
- [x] **Implement** `src/engine/config.py` — `GameConfig` + `load_config()`,
      reading only `config/game.json`, no duplicated literals.
- [x] Confirm they **pass** (3 passed; grep confirms no literal game values).
      Under the limit at 66 lines (grown with the scoring/pheromone/league blocks).

### 0.3 `actions.py` (→ `errors.py`)

- [x] **Test first**: `tests/engine/test_actions.py` — the `Action` enum has
      exactly `N, S, E, W, STAY`; `parse_action` maps each token; any other token
      (including lowercase) raises `InvalidActionError`; each action maps to the
      correct `(row, col)` delta.
- [x] Confirm the tests **fail**.
- [x] **Implement** `src/engine/actions.py`. *Architecture note:* it depends only
      on `errors.py`, not `config.py` — the enum is the vocabulary definition, and
      a **drift-guard test** asserts `[a.name for a in Action] ==
      GameConfig.move_set` so `config/game.json` stays the source of truth without
      runtime coupling.
- [x] Confirm they **pass** (10 passed; suite 19). 55 lines.

### 0.4 `board.py` (→ `config.py`, `errors.py`)

- [x] **Test first**: `tests/engine/test_board.py` — bounds are correct for all
      `r, c ∈ [0,6]` and false outside; `is_barrier` is false before placement and
      true after; placing on an occupied cell raises
      `IllegalBarrierPlacementError`; a 15th barrier raises `BarrierLimitError`
      and does not increment the count.
- [x] Confirm the tests **fail**.
- [x] **Implement** `src/engine/board.py` — sized from `GameConfig`, no literal
      `7` or `14`. *Design:* `place_barrier(pos, occupied=())` takes occupancy
      from the caller so `Board` stays decoupled from `player.py`; barriers live
      in a `set`; the occupancy check precedes the cap check.
- [x] Confirm they **pass** (11 passed; suite 30). 75 lines.

### 0.5 `player.py` (→ `actions.py`)

- [x] **Test first**: `tests/engine/test_player.py` — `PlayerState` holds
      position and role; `intended_position` applies the delta with **no**
      bounds/barrier awareness (it may return an off-grid coordinate, by design);
      `STAY` returns the position unchanged; the function is pure and does not
      mutate `state`.
- [x] Confirm the tests **fail**.
- [x] **Implement** `src/engine/player.py`, reusing `action_delta` from
      `actions.py` (no re-hardcoded deltas).
- [x] Confirm they **pass** (9 passed; suite 39). 36 lines.

### 0.6 `resolver.py` (→ `board.py`, `player.py`, `actions.py`) — locked FR5

- [x] **Test first**: `tests/engine/test_resolver.py` covering all seven FR5
      cases — both unobstructed; cop out of bounds → `STAY` with the thief
      unaffected; thief onto a barrier → `STAY` with the cop unaffected; both
      blocked simultaneously; same-cell capture (case a); swap capture (case b);
      adjacent near-miss → no capture; and the case where a move first resolves
      to `STAY` and *then* coincides with the opponent's new position → capture
      still detected on the **resolved**, not intended, positions.
- [x] Confirm the tests **fail**.
- [x] **Implement** `src/engine/resolver.py` — `TurnResult` + `resolve_turn()`,
      steps 1–3 of FR5, implemented here and nowhere else.
- [x] Confirm they **pass** (11 passed; suite 50). *Independently re-run with 7
      adversarial scenarios — follow-vs-swap in both directions, barrier-STAY
      capture, no false-positive swaps. Capture logic confirmed present only in
      `resolver.py`; inputs verified unmutated.* 90 lines.

### 0.7 `game_loop.py` (→ all of the above)

- [x] **Test first**: `tests/engine/test_game_loop.py` — `reset()` places both
      agents at their configured starts with turn count 0; malformed tokens raise
      `InvalidActionError` without mutating state; a valid `step()` advances the
      count by exactly 1 and appends one history entry; the returned `TurnResult`
      matches what `resolve_turn` would produce (no divergent logic); termination
      fires immediately on capture and no later `step()` mutates state;
      termination on `max_moves` fires at exactly 35, not one turn early or late;
      `history` is ordered and complete; and **FR7 determinism** — `replay()` run
      twice over the same recorded sequence produces value-identical history.
- [x] Confirm the tests **fail**.
- [x] **Implement** `src/engine/game_loop.py`. *Positions normalised to tuples
      (config starts are JSON lists — avoids the `(0,0) == [0,0]` False bug);
      capture and resolution fully delegated to `resolve_turn`; a `step()` on a
      terminated episode is a no-op.*
- [x] Confirm they **pass** (13 passed; suite 63). *FR6 timing independently
      verified (not terminated at 1..34, terminated exactly at 35) and FR7
      determinism across fresh and re-replayed episodes including a mid-episode
      capture.* 106 lines.

### 0.8 Phase-0 closeout

- [x] Run the full `tests/engine/` suite together — no interaction or
      order-dependence issues.
- [x] Batch re-check: every file under `src/engine/` is ≤150 lines.
- [x] Grep `src/engine/` for literal hyperparameters (`7`, `14`, `35`, `"STAY"`
      …) used as magic numbers — none outside `config.py` and its fixtures.
- [x] Walk one full 35-turn episode end to end; FR6 fires at exactly turn 35.
- [x] Walk one scripted capture-by-swap episode; FR5 case (b) surfaces at the
      episode level, not only in the resolver's unit tests.

---

## Phase 1 — Distributed P2P Infrastructure (FastMCP)

- [x] **Phase-0 addendum (authorised reopening)**: extend `GameConfig` with the
      `network_and_league` timeout fields (`response_timeout_sec`,
      `watchdog_timeout_sec`) — test first, then implement.
- [x] Scaffold `src/mcp_server/` and its test package.
- [x] Machine-level multi-agent environment setup; **no secrets committed**.
- [x] **Test first, then implement** `observations.py` — pure view functions
      building the observation and status payloads from `MatchState` + config.
- [x] **Test first, then implement** `action_buffer.py` — the two-slot per-turn
      buffer, with an injectable clock and lazy staleness expiry.
- [x] **Test first, then implement** `match_state.py` — the locked async
      mechanism over a real `GameEpisode`:
  - [x] A single `asyncio.Lock` guards the read-modify-step sequence, so exactly
        one `GameEpisode.step` fires per turn under concurrent submission (FR8) —
        proven by a concurrency test, not by inspection.
  - [x] Rejection codes `invalid_role`, `invalid_direction`, `already_submitted`.
  - [x] Lazy wall-clock timeout, never a blocking sleep.
  - [x] `terminal_reason()` returns `capture` / `max_moves_reached` /
        `technical_loss` / `None`, with a real game outcome **outranking** a
        forfeit so a late stall check cannot relabel a finished match.
  - [x] Forfeit state moved out of `SubmissionGate` and onto `MatchState` (audit
        V5), so `get_observation` and `get_match_status` can no longer disagree
        about whether the match is over.
- [x] **Test first, then implement** `transport.py` — per-peer `[network]`
      settings loader (`host`, `my_port`, `opponent_url`, `public_url`).
- [x] **Test first, then implement** `server.py` as a composition root only, with
      one independent FastMCP app, config directory and `GameEpisode` per peer —
      the mirrored-local-truth topology (D2), zero shared memory between peers.
- [x] Split `tools.py` out of `server.py` **before** the 150-line limit was
      reached, per the constitution.
- [x] **Test first, then implement** `peer_processes.py` — spawn both peers as
      real OS processes, wait on their ports, and **always** tear them down, so a
      crashed match cannot leave a listener bound for the next run to talk to.
- [x] **Test first, then implement** `http_peer.py` + `peer_client.py` — real
      streamable-HTTP tool invocation between the two peers.
- [x] **Test first, then implement** `run_local_mcp_match.py` — the two-peer
      harness, removing the external dependency that blocked Step 7b by playing
      both peers locally over a real transport with crypto fully in force.
- [x] Port assignment locked to **thief 8801 / police 8802** across all three
      sources (`config/thief/game.toml`, `config/police/game.toml`,
      `config/declaration.json`), guarded by
      `tests/mcp_server/secure/test_declaration_agrees_with_transport.py`.
- [x] **Two-repository isolation** — `zero-trust-cop` and `zero-trust-thief` as
      independent, separately-clonable repositories with no shared memory, file
      or database table at runtime; isolation enforced at the repository,
      process, state and configuration levels (`PLAN.md` §2).
  - [x] Reciprocal `README.md` §0 cross-links, present as both a table row and a
        prose callout on each side, per the submission guidelines.
  - [x] `[game.repos]` declared once per peer and emitted into
        `declaration_<game_id>.json` and `result_<game_id>.json`, so a marker
        holding either artifact can find the other half of the pair.
  - [x] `scripts/thief_readme.py` regenerates the thief README from anchors and
        **fails loudly** if any cross-link anchor stops matching — after a manual
        conversion once left two inconsistent cross-link tables.
- [x] **Test first, then implement** `tunnel.py::parse_public_url` — empty is
      legal; ngrok and Localtonet `http`/`https` accepted; trailing slash and
      whitespace normalised; bare host, `tcp://`, `//host` and host-less
      rejected. Routed through `load_network_settings` so an invalid configured
      `public_url` raises at load rather than mid-match.

---

## Phase 2 — Lockstep Commit-Reveal State Machine

- [x] Extract the single canonical serialisation (`crypto.canonical_json`) so
      every signed or hashed payload has exactly one byte representation.
- [x] Add the Ed25519 dependency (`cryptography`).
- [x] **Git-ignore key material BEFORE any key exists** — ordering was the point;
      `.gitignore` landed first, then `keygen.py`.
- [x] **Test first, then implement** `identity.py` — Ed25519 `sign` /
      `verify_signature` over `canonical_json({"role", "turn", "h_commit"})`, hex
      encoded. The turn number is bound into the signed message so a captured
      signature cannot be replayed on a later turn.
- [x] **Test first, then implement** key loading with workspace separation —
      `config/<role>/signing_key.pem` and `config/<role>/peers/<peer>.pub`;
      a public key must be 32 bytes of valid hex or loading fails loudly.
- [x] **Test first, then implement** `keygen.ensure_keys` — generate any missing
      key material on first run, and report what it created.
- [x] **Test first, then implement** `crypto.commit` / `crypto.verify`:
  - [x] `h_commit = SHA256(State || Move || Intent || Nonce)` — literal
        positional concatenation per Rulebook 5.3, because a divergence here
        breaks cross-group interop and **cannot be detected by either group
        alone**.
  - [x] 128-bit `secrets.token_hex` nonce, fresh per commitment.
  - [x] `secrets.compare_digest` rather than `==`, so no timing gradient toward a
        colliding reveal is leaked.
  - [x] The superseded canonical-JSON payload form still *verifies* (so
        pre-alignment artifacts stay checkable) but is no longer emitted —
        `tests/unit/test_positional_digest.py`.
- [x] **Test first, then implement** `commitments.py::CommitmentBook` — the
      lockstep phase machine `empty → half → both_committed → half_revealed →
      resolved`, with every transition rule from `PLAN.md` §3 pinned by a test:
  - [x] A reveal before both commitments are in is refused as
        `reveal_before_commit` — the load-bearing rule of the whole protocol.
  - [x] `already_committed` / `already_revealed` — one of each per role per turn.
  - [x] `stale_turn` below the current turn; a higher turn rolls the book forward
        and clears commitments, moves and the deadline.
  - [x] `broken_commitment` when the revealed tuple does not reproduce the digest
        — the move never reaches the engine.
  - [x] `stalled_roles()` starts its deadline at the **first** commitment and
        attributes blame to the phase actually blocked (D7): while a commitment
        is outstanding only the silent committer is at fault, because its
        opponent's reveal is *refused* by rule 1 and so it is blocked, not
        stalling.
- [x] **Test first, then implement** `submissions.py::SubmissionGate` — the
      authenticated pipeline: signature verification precedes the commitment
      book, stall expiry runs on the read tools.
- [x] **Test first, then implement** `directions.py` — the wire vocabulary
      (`encode`/`decode`/`is_wire_move`) and stated hints.
- [x] Wire the four-tool surface into `server.py` (the deferred Step 7b):
      `get_observation`, `submit_commitment`, `reveal_move`, `get_match_status`.
  - [x] The plaintext `make_move` tool is **removed**: it accepted an unsigned
        direction from any caller under any role with nothing binding it to a
        prior commitment (D3).
  - [x] A peer's own identity is read from the captured `own_role`, never from
        the caller-supplied `role` argument.
  - [x] Tool parameter names documented as the wire contract — FastMCP derives
        the public input schema from the signature, so a rename is a protocol
        change.
- [x] **Test first, then implement** `match_loop.py::play_match` — broadcast both
      commitments to every peer, **then** both reveals, so the phase separation
      is exercised over the real transport.
- [x] **Test first, then implement** `match_loop.py::divergence` — compare both
      peers' independent engines every turn on `turn_count`, `cop_position`,
      `thief_position`, `captured`, `is_terminated`; raise `DivergenceError`
      rather than absorbing a disagreement.
- [x] **Test first, then implement** the Step-0 computational-fairness
      declaration (FR6) — `declaration.py` probing CPU / RAM / GPU VRAM / OS /
      timezone / commit hash, with **declared** fields failing loudly and
      **probed** fields degrading to `unknown` / `none`, so host inspection can
      never prevent an artifact from existing.
  - [x] Documented in `PLAN.md` §5 and §10 that this artifact is **unsigned and
        unenforced** — a claim, not proof of fairness.
- [x] Phase-2 cross-cutting verification: no key material tracked; every
      protocol rejection path has a test; the whole surface exercised end to end
      over streamable HTTP.

---

## Phase 3 — AI Brain & Game Physics

- [x] **Test first, then implement** `strategy/settings.py` — the `[strategy]`
      loader, so no learning hyperparameter is ever a literal in Python.
- [x] **Test first, then implement** `strategy/qvalues.py`:
  - [x] Exact TD update `Q(s,a) ← Q(s,a) + α(r + γ·max Q(s',a') − Q(s,a))`, with
        the bootstrap term omitted on terminal transitions — asserted
        arithmetically, not approximately.
  - [x] State key `(relative_opponent, barrier_mask)`: displacement is relative
        so one entry generalises across the board; the 4-bit mask treats
        off-board neighbours as blocked; `move_count` is **excluded** because
        including it would make every turn a distinct state and destroy
        generalisation.
  - [x] Rewards sourced from the shared `scoring` block (capture cop 20 / thief
        5; survival cop 5 / thief 10; tie 2; technical loss 0), rejecting unknown
        role/outcome vocabulary.
  - [x] `best_action` retains `move_set` tie order, keeping selection
        deterministic.
  - [x] Exploration decay (D1): `epsilon_decay_factor = 0.999` clamped at
        `epsilon_floor = 0.01`.
  - [x] JSON persistence behind `STATE_LAYOUT_VERSION = 1`; a version mismatch
        raises rather than loading incompatible keys. Round-trip tested.
- [x] **Test first, then implement** `strategy/pheromones.py` — the thief scent
      trail:
  - [x] Recurrence `τ(t+1) = max(0, (1−ρ)·τ(t) + δ)`, with the `max(0, …)` clamp
        proven under the signed direct-delta path.
  - [x] τ₀ = `0.90` and ρ = `0.10` read from `config/game.json`, never inlined.
  - [x] The 5×5 window stamps a **13-cell Manhattan diamond** — exact kernel
        values by distance asserted (`0.90 / 0.60 / 0.30`), the four box corners
        left at zero.
  - [x] Edge kernels are **clipped**, never wrapped or redistributed.
  - [x] Odd, positive `pheromone_grid_size` validated at construction.
  - [x] `strongest()` returns the maximum-concentration cell, or `None`.
- [x] **Test first, then implement** `strategy/belief.py::BeliefTracker` —
      stated-intent honesty as `honest` / `dishonest` / `unscorable`, where an
      unscorable intent is *absent* evidence and never moves the rate;
      word-boundary matching so `SNOW` and `NEWS` do not name directions; the
      configured `honesty_prior` returned when there is no scorable evidence.
- [x] **Test first, then implement** `agent/agent_core.py::AgentPolicy` — the
      policy layer over the strategy modules:
  - [x] The D2 hybrid opponent source (resolved position → `pheromones.strongest()`)
        is resolved **inside** `state_key`, so no caller can skip the fallback.
  - [x] Cop states its intent honestly; thief **inverts** it, giving the belief
        tracker a real signal to score.
  - [x] Intent truncated to `hint_max_words = 15`.
  - [x] Exactly one `qvalues.update` per transition, and exactly one pheromone
        deposit per observation.
- [x] **Test first, then implement** `scripts/run_tournament.py` +
      `tournament_loop.py` — the offline batch trainer.
- [x] Execute the real training run (2000 games per role) and commit
      `data/q_table_police.json` and `data/q_table_thief.json`.
- [x] **Test first, then implement** `peer_policy.build_peer_policy` — load the
      trained table into each live peer at **`match_exploration_rate = 0.0`**
      (D5: competitive play is purely greedy).
- [x] Import-direction guard: `strategy/` and `engine/` never import from
      `mcp_server/`.

---

## Phase 4 — Observability & Reporting

- [x] **Test first, then implement** `scripts/match_log.py` — the four artifacts
      under `logs/<group_id>/`: `declaration_*`, `config_*`, `log_*`, `result_*`.
  - [x] Deterministic JSON (`indent=2`, `sort_keys=True`, trailing newline) so
        repeated runs are **byte-identical**.
  - [x] The log carries every digest, signature and revealed tuple, so it is
        **sufficient for replay on its own** — a verifier needs nothing but the
        file and the peers' public keys.
  - [x] The shared config is **copied, not referenced**, and stamped with
        `game_uid`, so the artifact records what the match actually ran under and
        all four files tie together.
  - [x] `mutual_agreement.confirmed` written only because `play_match` compared
        both engines every turn — the history that reached the writer *is* the
        evidence.
  - [x] Schema caveat recorded in-module and in `PLAN.md` §7.1: only the four
        *filenames* come from the specification; the field layout is this
        project's own design pending reconciliation with Appendix F.
- [x] **Test first, then implement** the replay verifier — and **prove it can
      fail**, which is the only thing that makes a passing verdict mean anything:
  - [x] `check_structure` + `check_turn_indices` + `check_intents`
        (`log_shape.py`).
  - [x] `check_commitments` — every digest re-derives from its revealed tuple.
  - [x] `check_signatures` — every signature re-verifies against that peer's
        public key **for the turn it claims**.
  - [x] `check_replay` — **per-turn** comparison plus the turn count (audit V1 /
        V3): an earlier version compared only the final state, so a fabricated
        match middle certified clean, and an unchecked count let turns be padded
        on after termination where `step()` is a no-op.
  - [x] Hostile field types produce a **verdict, not a traceback** (audit V4):
        every check appends to a shared failures list instead of raising, and
        `verify_log` wraps the lot — `tests/unit/test_log_check_safety.py`.
  - [x] `Verified OK` / `TAMPERED!` with a non-zero exit on failure; colour
        suppressed when not a TTY or when `NO_COLOR` is set, so piped output
        stays byte-clean.
  - [x] Negative tests: tampered middle turn, padded turn count, non-contiguous
        index, hostile type, and a clean log — each asserted against its exact
        verdict.
- [x] **Test first, then implement** `gui/` — `board_canvas.py`, `board_view.py`,
      `palette.py`, `replay.py`, `live_heatmap.py`, `scripts/render_replay.py`,
      `scripts/heatmap.py`.
  - [x] The replay viewer's badge is driven by the **same** `verify_log` the
        headless CLI uses, so the window cannot disagree with
        `scripts.replay_match`.
  - [x] Frames are reconstructed from the logged **moves**, not the recorded
        positions, so a forged log is drawn as it truly replays.
  - [x] The live heatmap auto-advances (700 ms) and shades by concentration;
        shading **clamps** rather than claiming a probability, since overlapping
        kernels exceed 1.0 (observed peak 2.41).
  - [x] Docstring records that the board is 7×7 and the 5×5 figure is the scent
        *kernel*, not the display size.
- [x] **Test first, then implement** `reporting/` — Gmail API delivery of the
      end-of-series result (Rulebook 34 / §9.3.3):
  - [x] `gmail_transport.py` — OAuth token handling and send.
  - [x] `mime_report.py` — `multipart/mixed` with exactly one
        `application/json` part named `result_<game_uid>.json`; the body is a
        summary and is kept **free of braces** so the no-plaintext-report rule is
        mechanically checkable (`tests/unit/test_email_attachment.py`).
  - [x] `email_sender.py` — policy: refuse to report unless
        `mutual_agreement.confirmed is True`, so a divergence can never be
        laundered into a submission.
  - [x] Modes `auto` / `draft` / `send`, where `send` reports failure rather than
        quietly drafting.
  - [x] Draft fallback writes summary **plus the decoded attachment**, so a
        missing credential never breaks CI and never loses the result it was
        trying to send (`tests/unit/test_email_fallback.py`).
- [x] Execute the full local simulation and commit the artifacts under
      `logs/aviayeli/`; `results/result_simulation.json` and
      `logs/email_draft_aviayeli.txt` recorded.
- [x] Match-summary output: `run_local_mcp_match` prints seed, turns,
      `terminal_reason`, `captured`, both final positions and `peers_agreed`, and
      the seed reproduces the match exactly.

---

## Phase 5 — Submission Housekeeping

### 5.1 Conformance corrections (`PLAN_07` / `TODO_07`) — complete

- [x] **Identity (FR1)**: `group_name` → `aviayeli` in `config/declaration.json`
      and `agreed_between[0]` in all three `game.json` copies;
      `logs/groupa` → `logs/aviayeli` with the four artifacts renamed and their
      internal `game_uid` / `game_id` / `group_id` rewritten; `results/`,
      `logs/email_draft_*`, `scripts/simulate_email_delivery.py`, the seven test
      modules and the README paths all updated.
  - [x] Gate: `scripts.replay_match logs/aviayeli/log_aviayeli_g01.json` still
        prints `Verified OK` — proving the rename left the crypto intact.
- [x] **Ports (FR2)**: test updated to cop 8802 / thief 8801 and confirmed
      failing first, then `[network]` swapped in both `game.toml` files and
      `mcp_servers` swapped in `config/declaration.json` until all three agree.
- [x] **Tunnel validation (FR2)**: `tests/mcp_server/secure/test_tunnel_urls.py`
      written and confirmed failing, then `tunnel.py::parse_public_url`
      implemented and routed through `load_network_settings`.
- [x] **Report attachment (FR3)**: `tests/unit/test_email_attachment.py` written
      and confirmed failing, then `mime_report.py` implemented and re-exported
      from `email_sender`; `test_email_sender`'s plain-text expectation inverted;
      `test_email_fallback` kept green; `gmail_transport.gmail_send` confirmed to
      need no change (`as_bytes()` already serialises a multipart correctly).
- [x] **Decay documentation (FR4)**: the geometric-vs-subtractive discrepancy and
      both configured constants documented in `strategy/pheromones.py`,
      `gui/live_heatmap.py`, README §7 and now `PLAN.md` §4.1 — **no behaviour
      change**; the pheromone tests were left untouched and green.

### 5.2 Repository gates — complete

- [x] `pytest -q` → **673 passed** *(as of Phase 5.2; the suite has grown since — see `PLAN.md` §11 and README §9 for the current total)*; no previously passing test regressed.
- [x] README self-checked figures (test total ×2, tracked file count,
      longest-file line count) updated and proven by
      `tests/unit/test_readme_consistency.py`.
- [x] 150-line audit over `git ls-files '*.py'` — longest is
      `strategy/qvalues.py` at 147.
- [x] `scripts/sync_repos.sh` — rebuild and re-gate the thief branch from the cop
      repository.
- [x] Push both remotes: `origin` (zero-trust-cop) and `thief`
      (zero-trust-thief); `master` has no unpushed commits.
- [x] Tag `v1.0-submission` created and **pushed to both remotes** —
      `origin` → `57b30a7`, `thief` → `3aa4195` (verified via
      `git ls-remote --tags`).

## Phase 6 — Audit Remedies

Closing the findings of the readiness audit. Each item was executed test-first:
the failing test is named, and where a remedy REVERSED an earlier accepted
ruling, the test that encoded the old ruling is named too.

### 6.1 Reward degeneracy — complete

- [x] **Penalise refused moves and wandering.** `step_cost = -0.01` added to
      both peers' `[strategy]` blocks (never inlined) and
      `tournament_loop.shaping_reward` applies it alongside the already-configured
      `invalid_move_penalty = -1.0` whenever a non-`STAY` move leaves an agent
      in the cell it started from. Red first: `tests/scripts/test_shaping_terms.py`
      (6 cases) and `test_strategy_settings_new_keys.py::test_step_cost_*`.
- [x] **Reversal recorded.** `test_sparse_rewards.py` asserted that every
      non-terminal transition learns from exactly 0.0 — the PLAN_05 "sparse
      terminal rewards only" ruling, which is what made wall-bumping free. It
      is renamed to `test_shaped_rewards.py` and now asserts the narrower
      invariant that actually matters: shaping never leaks into the reported
      GAME SCORE, and zeroing both terms restores the old signal exactly.
- [x] **Retrained** 2,000 episodes at `--seed 20260801`: captures 1713 → 1994,
      first-200-game capture rate 10.5% → 97.5%. Tables reproduce byte-for-byte
      from the seed (verified by `sha256sum` before/after a re-run).
- [x] **Flagship log regenerated** — 5 turns → 3, and the turn-0 cop move is
      `E` from `(0,0)` instead of a blocked `N`. No turn in the new log spends a
      move immovable on row 0. `scripts.replay_match` → `Verified OK`.

### 6.2 Clean-checkout key protection — complete

- [x] **`ensure_keys` refuses to overwrite a shipped `.pub` whose `.pem` it had
      to generate**, which is exactly the state of a fresh clone, and announces
      the refusal on stdout. Red first:
      `tests/mcp_server/secure/test_keygen_protection.py` (7 cases).
- [x] **Reversal recorded.** `test_keygen.py::test_a_regenerated_key_republishes_its_public_half`
      asserted the opposite — that a stale `.pub` must never survive. It is
      narrowed to the case where nothing was shipped, and the trade-off (live
      play on a clone is signature-rejected until keys are restored) is stated
      in `PLAN.md` §10.8 and the module docstring rather than glossed.

### 6.3 Network watchdog — complete

- [x] **`watchdog_timeout_sec` enforced** on every `HttpPeer` wire call via
      `asyncio.wait_for`, raising `TechnicalLossError` on expiry instead of
      hanging the tournament. The deadline is a required constructor argument,
      so no call site can silently reintroduce the hang. Red first:
      `tests/mcp_server/secure/test_peer_watchdog.py` (7 cases).

### 6.4 Reporting fallback — complete

- [x] **`mode = "auto"`** in both `[email]` blocks, so a grader without Google
      credentials gets a valid local draft rather than a failed run. Recipient
      confirmed as `rmisegal+uoh26finalgame@gmail.com`. Red first:
      `tests/unit/test_shipped_email_config.py`.
- [x] `match_report.py` split out of `run_local_mcp_match.py`, which the
      watchdog wiring had pushed to 153 lines.

### 6.5 Documentation honesty — complete

- [x] **`PLAN.md` §4.1, §4.2 and §10.4 rewritten** to state where the scent
      trail actually runs: it supplies the turn-0 belief in offline training
      and is rebuilt from the log to drive the replay heatmaps, while live
      league play uses direct coordination over FastMCP and never reaches the
      fallback. Verified against the code, not asserted: `observe_opponent` has
      exactly one caller (the offline trainer) and `strongest()` is reached
      only when no resolved cell was supplied.
- [x] **README corrected** — the replay transcript showed `move=E
      intent='east'`, which the wire has never carried; the real log records
      `MOVE:E` with an honesty flag of `truth`/`lie`. Regenerated from actual
      output, along with every retraining-dependent figure.

## Phase 7 — Final administrative submission — pending

- [ ] Export the submission document to PDF (README / architecture write-up,
      including the `Verified OK` verifier transcript and the GUI screenshots
      under `docs/screenshots/`).
- [ ] Upload the PDF to **Moodle**.
- [ ] Submit both repository URLs and the `v1.0-submission` tag reference on the
      Moodle form.
- [x] Reporting **configuration** verified: recipient
      `rmisegal+uoh26finalgame@gmail.com` and `mode = "auto"` are set in both
      peers' private `[email]` blocks, and the send/draft policy is covered by
      `tests/unit/test_shipped_email_config.py` and `test_email_fallback.py`.
      This is the config, NOT the delivery — the item below remains open.
- [ ] Confirm the graded email report was received at the course address. The
      regenerated flagship match (2026-08-11) reported under `mode = "auto"`
      with valid credentials on disk and printed `email_report=ok`, so a real
      message was delivered rather than drafted; `logs/email_draft_aviayeli.txt`
      is the older fallback record, not evidence of this run.
- [ ] Reconcile the `config` / `log` / `result` field layouts against
      **Appendix F** of `police_thief_p2p.pdf` once the appendix is available
      (see `PLAN.md` §7.1 and §10.5).
- [ ] Play a live **cross-group league match** against the opposing group's
      peers, replacing the local two-peer simulation (see `PLAN.md` §10.7).

## Phase 8 — Off-manifold generalisation & repository sync — complete

**Lifecycle note, recorded rather than hidden:** the work below was implemented
BEFORE it was entered here, which inverts the `PRD -> PLAN -> TODO` order this
project's `CLAUDE.md` mandates. `PLAN.md` §10.10 was likewise written after the
code it describes. These entries are therefore a retroactive record, not
evidence of a tracked design cycle, and are marked as such so the log does not
overstate the process that produced them.

### 8.1 Distance-tiebreak fallback — complete

- [x] **Failing tests first** for a greedy Manhattan tie-break on states where
      every action is exactly `0.0` (`tests/mcp_server/test_qvalues_fallback.py`,
      9 cases): cop minimises distance, thief maximises, blocked moves refused,
      `STAY` chosen when every direction is blocked.
- [x] `strategy/fallback.py` added, owning `BARRIER_BIT_DIRECTIONS` so the
      mask's writer and reader cannot drift apart. `qvalues.py` defers to it and
      stays within the 150-line limit at 149.
- [x] Role wired at BOTH production sites — `mcp_server/peer_policy.py` and
      `scripts/run_tournament.py` — each pinned by a test, since a table built
      without a role silently disables the fallback.
- [x] Flagship trajectory proven unchanged: the published starts still play
      `E/N -> S/W -> E/N` and capture on turn 3, and `scripts.replay_match`
      still returns `Verified OK` on the shipped log.

### 8.2 Reproducible off-manifold benchmark — complete

- [x] `scripts/offmanifold_probe.py` (sampling, episodes, aggregation) and
      `scripts/benchmark_offmanifold.py` (published run + CLI), split before
      either reached the line limit.
- [x] Sample size, seed and opponent set in `config/benchmark.json`, so no
      benchmark tunable is inlined in Python.
- [x] `PLAN.md` §10.10 published with the MEASURED result, including the
      finding that the fallback does **not** reach heuristic parity (69.2% vs
      98.2% against the trained thief) and that no cop catches a greedy evader.
- [x] Every figure §10.10 prints is re-derived from a real run by
      `tests/scripts/test_benchmark_plan_claims.py`, so a retrain fails the
      suite rather than stranding the prose.

### 8.3 Dual-repository sync and documentation integrity — complete

- [x] `scripts/thief_readme.py` rule 6 realigned to the retrained 200-game
      matrix. The stale anchor had been failing since 2026-08-11, which stopped
      every sync and left both remotes byte-identical on `4b338c8`.
- [x] Whole conversion moved into the suite (`tests/unit/test_thief_readme.py`),
      turning a push-time failure into a test-time one — `sync_repos.sh` gates
      on pytest before converting.
- [x] `STRATEGY_BLOCK`'s thief-table figures corrected from 128 entries / 46
      states / 4.9968 to the true 391 / 144 / 4.9999, and now verified against
      `data/q_table_thief.json` at runtime (`tests/unit/test_thief_figures.py`)
      — inserted content had no anchor, so nothing caught the drift.
- [x] `mcp_server/crypto.py` docstring reconciled with the shipped system: it
      claimed "peer identity remains unauthenticated" while `identity.py` has
      signed both protocol phases since 2026-07-25, contradicting §10.6.
- [x] Both remotes verified **distinct** and tag-aligned by the script's own
      guards (cop `master` != thief `master`, each tag on its own head).

## Phase 9 — Barrier activation (S-1 / S-2) — in progress

`max_barriers: 14` has been configured since Phase 0 and populated never:
every play path built a bare `Board`, so `place_barrier` had no caller outside
its own tests. The measured cost is in `PLAN.md` §10.10 — **0.0% capture
against a greedy Manhattan evader for all four policies**, because a bare 7x7
grid under simultaneous moves gives a lone pursuer nothing to corner against.
Architecture in `PLAN.md` §4.3.

### 9.1 Deterministic layout generator — complete

- [x] **Test first**: `tests/engine/test_barriers.py` — exactly `max_barriers`
      cells; identical for one config and different across seeds; never on
      `cop_start` or `thief_start`; every cell in bounds; `barrier_seed: null`
      yields an empty layout; and the free space is connected with both starts
      inside it.
- [x] Confirm the tests **fail** (module does not exist).
- [x] **Implement** `src/engine/barriers.py` — `barrier_layout(config)`,
      resampling under a deterministic counter until connectivity holds.
- [x] `barrier_seed` added to `movement_and_barriers` in all three
      `game.json` copies and to `GameConfig`; no seed or count in Python.

### 9.2 Wiring into the play and training paths — complete

- [x] **Test first**: `GameEpisode.reset()` places the configured layout;
      `reset()` is idempotent; a bare-seed config still yields `barrier_count`
      of 0.
- [x] `GameEpisode.reset()` populates its board from `barrier_layout`, which
      makes the trainer, the server and the probe agree without any of them
      knowing how a layout is built.
- [x] `run_local_mcp_match.py`'s client-side `Board` populated from the same
      function, so the policy's `barrier_mask` matches the engine that resolves
      it — they were separate `Board` objects that only agreed while both were
      empty.
- [x] `offmanifold_probe.py` passes the episode's real barrier set to
      `state_key` instead of the hardcoded `set()`.

### 9.3 Replay compatibility for pre-Phase-9 evidence — complete

- [x] **Test first**: a log carrying `barriers` replays against that layout; a
      log without the key replays bare; the shipped flagship log still verifies.
- [x] `build_log` records the layout; `check_replay` reconstructs from it and
      falls back to a bare board when the key is absent.
- [x] `scripts.replay_match logs/aviayeli/log_aviayeli_g01.json` →
      `Verified OK`, with the artifact unmodified (`PLAN.md` §10.10,
      *Provenance of the shipped evidence*).

### 9.4 Retraining and re-measurement — complete

- [x] Both tables retrained on the barriered board (`--seed 20260801`,
      2000 games): 1997 captures, a 99.85% series rate.
- [x] State-space coverage measurably enriched — the point of the phase:
      thief 144 -> 230 states (391 -> 556 entries), cop 177 -> 233 states.
      The cop's ENTRY count fell (508 -> 369) while its state count rose:
      walls prune unreachable relative-offset/mask combinations faster than
      they add new ones.
- [x] `scripts.benchmark_offmanifold` re-run; `PLAN.md` §10.10's matrix and
      every derived figure rewritten from that run.
- [x] **Two published findings REVERSED and rewritten rather than quietly
      dropped:** the greedy evader went 0.0% -> 47.2%, and the learned table
      turned from a 13.5-point NET NEGATIVE tie-breaker into a +4.0 (trained)
      / +17.0 (greedy) NET POSITIVE.
- [x] The claim tests were rewritten to pin the new direction, including one
      that reconstructs the bare board to prove the barriers are the cause.
- [x] Live two-process match on the barriered board: capture on turn 4,
      `peers_agreed=True` — the client board and both engines agree.
- [x] `pytest -q` → **782 passed**; `scripts.replay_match` → `Verified OK`
      on the unmodified flagship log.

## Phase 10 — Protocol-surface hardening (T-1) — complete

- [x] **Test first**: `tests/mcp_server/test_crypto_legacy_gate.py` — a
      legacy-sealed digest is refused by default and accepted only under
      `allow_legacy=True`; the positional form verifies either way; the flag
      cannot be passed positionally; a wrong digest still fails with the gate
      open; and `CommitmentBook.reveal` — the live protocol path — refuses a
      legacy-sealed commitment outright.
- [x] Confirm the tests **fail** (five of six; the sixth passed only because
      the keyword did not exist yet).
- [x] **Implement** the keyword-only `allow_legacy` gate in
      `mcp_server/crypto.py`, defaulting to `False`.
- [x] `scripts/log_checks.py` and `scripts/render_replay.py` — the two readers
      of sealed history — opt in explicitly. No protocol-path caller does.
- [x] The two pre-existing legacy tests rewritten to pin BOTH directions
      rather than only that legacy still works.
- [x] `scripts.replay_match logs/aviayeli/log_aviayeli_g01.json` →
      `Verified OK`; the flagship artifact is unmodified.
