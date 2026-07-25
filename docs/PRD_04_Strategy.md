# PRD 04 — Strategic Engine (Phase 4)

## Status

DRAFT — awaiting Conductor + Judge approval. No implementation until approved.
Phase 3 Step 7b remains separately blocked on interop agreement; Phase 4 does not
depend on it.

## Objective

Give each peer an algorithmic basis for choosing moves — value estimation from
experience, opponent-trace tracking, and a measure of how much to trust what the
opponent says — so the agent plays competently without depending on an LLM for
tactical decisions.

## Scope

In scope: a reinforcement-learning value store with episode updates, a pheromone
field for trace tracking, and a belief engine scoring opponent honesty.

Out of scope: wiring any of this into `server.py`'s tool surface (that follows
7b), LLM prompting, and opponent modelling beyond the honesty rate in FR9.

## Constraint That Shapes The Whole Phase

Three subsystems cannot share one 150-line module. The constitution requires
splitting *before* the limit is reached, so Phase 4 is three modules plus a
config prerequisite from the start:

```
src/strategy/pheromones.py   FR7 — trace field
src/strategy/qvalues.py      FR5/FR6 — value store and update rule
src/strategy/belief.py       FR9 — opponent honesty
```

## Source of Truth

- Pheromone recurrence: Chapter formula, reproduced verbatim in FR7.
- Reward weights: `config/game.json` → `scoring`.
- Pheromone parameters: `config/game.json` → `pheromones`.
- Partial observability: `PRD_02` FR3 — a peer never sees the opponent's position.

## Functional Requirements

### FR1 — Prerequisite: expose the `pheromones` block through `GameConfig`

`config/game.json` already carries `pheromone_decay: 0.1`,
`pheromone_center_intensity: 0.9`, `pheromone_grid_size: 5`, but `load_config`
drops the block, so ρ is unreachable from code. Hardcoding it would violate the
no-hardcoded-hyperparameters rule.

Additive extension to `GameConfig`, mirroring the authorized reopening that
`TODO_02` Task 0 performed for the timeout fields. Existing fields and parsing
are untouched.

### FR2 — RL hyperparameters live in the peer's PRIVATE `game.toml`

Learning rate, discount factor, exploration rate and the Q-table persistence path
are tunable and must not be literals in source. They go in the peer's own private
`config/<role>/game.toml`, under a `[strategy]` block.

Rationale: `config/game.json` carries `schema_version` and `agreed_between:
["groupa","groupb"]` — it is the shared, signed contract. Learning parameters are
private to a peer and must not perturb a file both sides parse.

Implementation notes:

- `config/<role>/game.toml` does NOT exist yet. Peer config today is
  `config/<role>/game.json`, and `server.py` hardcodes
  `_CONFIG_FILENAME = "game.json"`. `game.toml` is therefore a NEW, additional
  private file for strategy settings; `game.json` is unchanged and keeps serving
  the engine.
- TOML is read with `tomllib` (Python 3.12 standard library, read-only). No new
  dependency, consistent with the no-numpy constraint.
- The file holds no secrets, so it is tracked. Per-peer separation mirrors the
  key and config layout already established.

### FR3 — Partial observability is binding on the state representation

This is a Dec-POMDP. The state MUST be derivable from what the acting peer can
actually observe. A state keyed on absolute `(cop_position, thief_position)` is
invalid — it would only be trainable against an oracle no real peer has.

Where opponent information legitimately comes from, verified against the code:

- `observations.build_observation` (`get_observation`) EXCLUDES the opponent's
  position entirely, per `PRD_02` FR3.
- `observations.build_move_resolved` DOES return both `cop_position` and
  `thief_position` once a turn resolves, per `PRD_02` FR4.

So fog-of-war applies *within* a turn — between commit and reveal — not across the
match. A peer knows the opponent's position as of the last resolved turn, and
nothing more recent.

This dependency is load-bearing: if `build_move_resolved` is ever changed to hide
positions, the FR4 state space silently degenerates to barrier data alone and every
stored Q-value becomes meaningless. Any such change must be treated as breaking
Phase 4.

### FR4 — Q-table state and action space

- Action space: `config/game.json` → `movement_and_barriers.move_set`, never a
  literal list.
- State: a deterministic, hashable tuple derived from observable features only
  (FR3). The exact feature tuple is `PLAN_04`'s decision and must be documented
  there, because changing it invalidates every stored value.

### FR5 — Value update rule

Standard Q-learning update, with α (learning rate) and γ (discount) from
`config/strategy.json`:

    Q(s,a) <- Q(s,a) + α * ( r + γ * max_a' Q(s',a') - Q(s,a) )

An unseen `(s,a)` defaults to a configurable initial value rather than raising.

### FR6 — Rewards come from config, plus shaping

- Terminal rewards from `config/game.json` → `scoring` (`capture_cop: 20`,
  `capture_thief: 5`, `survival_cop: 5`, `survival_thief: 10`, `tie_score: 2`,
  `technical_loss: 0`), selected by the peer's role and outcome.
- Shaping penalties for a move into a barrier or off-board, and for a rejected
  submission. Magnitudes configurable, never literals.

### FR7 — Pheromone field

Exact recurrence, applied per cell:

    τij(t+1) = max(0, (1-ρ) * τij(t) + Δτij)

- ρ = `pheromone_decay` (FR1). Δτ deposited where a trace is observed, with
  intensity `pheromone_center_intensity`.
- `max(0, ...)` is not decorative: it must be enforced so no cell ever holds a
  negative concentration, including when Δτ is negative.
- Decay applies to **every** cell each tick, deposit only to observed cells.
- `pheromone_grid_size: 5` is ambiguous against a 7×7 board. `PLAN_04` must
  resolve and record whether it is the side length of a deposit kernel centred on
  the observed cell or a coarser overlay grid. Do not guess silently.

### FR8 — Q-table persistence

The table survives between matches, written to the path in
`config/strategy.json`. Loading a table whose state-feature layout does not match
the current code must fail loudly rather than silently mixing incompatible values
(the FR1 lesson from Phase 3: a wrong-shaped input that loads successfully is
worse than one that crashes).

### FR9 — Belief engine: intent-vs-move consistency

The deception channel already exists. Commit-reveal binds `intent` to the move it
accompanies (`crypto.py`), and `config/game.json` sets
`world.hint_max_words: 15`, so `intent` is the natural-language hint.

- Per opponent, record each revealed `(intent, move)` pair and whether the intent
  was consistent with the move actually played.
- Expose an honesty rate, starting from a configurable prior so a peer with no
  history is neither trusted nor condemned outright.
- Consistency is judged by matching direction tokens in the intent text against
  the revealed move. Intent that expresses no direction is UNSCORABLE and must
  not count as either honest or dishonest — silence is not a lie.
- This measures only *stated intent versus action*. It cannot detect a peer whose
  intent is honest and whose strategy is simply good, and it must not be described
  as lie detection.

Because commitments are cryptographically bound, an opponent cannot retroactively
alter what it claimed. The evidence is authentic and unforgeable — which is what
makes this measurable at all.

## Non-Functional Requirements

- Every Python file at or under 150 lines.
- Strict TDD: a failing test precedes every implementation change.
- No hardcoded tunables. Every weight, rate and threshold from config.
- Determinism: given a fixed table, config and seed, move selection must be
  reproducible. Exploration draws from an injectable RNG so tests are not flaky.
- No new dependencies. The standard library is sufficient; no numpy.

## Acceptance Criteria

- [ ] `GameConfig` exposes the pheromone fields; all existing config tests pass.
- [ ] No strategy module reads a tunable from a Python literal.
- [ ] Pheromone decay matches the FR7 recurrence on hand-computed vectors, and no
      cell can go negative.
- [ ] A Q-value update moves toward the target by exactly α × TD-error.
- [ ] The state tuple contains no opponent position (FR3), asserted by test.
- [ ] Rewards trace to `config/game.json` → `scoring`, not to literals.
- [ ] A persisted table with a mismatched feature layout fails loudly on load.
- [ ] Honesty rate is the configured prior with no observations; direction-free
      intent is unscorable rather than counted.
- [ ] Move selection is reproducible under a seeded RNG.
- [ ] Full suite green; no file over 150 lines.

## Series Length — Open Config Discrepancy

Tabular Q-learning is well justified: the guidelines book mandates a **6-game
series**, so the table accumulates real experience across games.

However `config/game.json` currently sets `num_games: 1`. That value is not
cosmetic — it is read by `declaration.py` (Step 8) into the Step-0 fairness
artifact, so a declaration generated today claims a 1-game series.

Not changed here, because `game.json` is the shared `agreed_between` contract and
altering it unilaterally affects the opposing group and the published declaration.
Flagged for an explicit decision: if 6 is mandated, `game.json` should be updated
and a fresh declaration emitted, ideally alongside the interop conversation that
Step 7b is already waiting on.

Within a single game the table still cannot learn usefully — 35 moves is not a
training run — so the module docstring must say that improvement comes across the
series, not within a match.

## Next Steps (Document Lifecycle)

1. Conductor + Judge approve this PRD.
2. Write `PLAN_04_Strategy.md`, resolving: the FR4 state feature tuple, the FR7
   `pheromone_grid_size` ambiguity, and the FR9 direction-token matcher.
3. Write `TODO_04_Strategy.md` from the approved plan.
4. Implement, strict TDD, one module per commit, FR1 first.
