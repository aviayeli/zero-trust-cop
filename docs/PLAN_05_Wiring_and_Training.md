# PLAN — Phase 5: Wiring and Training

## Status

DRAFT for review. No PRD_05 yet; if this plan is approved its content should be
promoted into one before implementation, per the document lifecycle.

Phase 4 built `pheromones.py`, `qvalues.py` and `belief.py`, each tested in
isolation and **consumed by nothing**. That is the same shape as `crypto.py`, which
sat verified-but-unwired for three commits in Phase 3 while front-running was
believed to be solved. This plan exists so the same gap is not mistaken for done a
second time.

Part A (wiring) is blocked behind Step 7b, since the live tool surface is where a
policy is invoked. Part B (offline training) is **not** blocked by 7b and can run as
soon as the agent layer exists.

## Objective

Give each peer a policy that consumes the strategy modules, and produce the
`data/q_table_*.json` deliverables from a genuine training series rather than test
fixtures.

## Non-Negotiable: the dependency direction

The core game logic must never learn that strategy exists.

```
      run_tournament.py  (offline batch trainer)  ──┐
      server.py          (live play, after 7b)   ──┤
                                                   ▼
                                            src/agent/   policy
                                            ┌──────┴──────┐
                                            ▼             ▼
                                     src/strategy/    src/engine/
                                  (pheromones,       (board, resolver,
                                   qvalues, belief)   game_loop)
```

Current state, verified rather than assumed:

- `src/engine/` imports nothing from `strategy` or `agent`.
- `src/strategy/` imports only `engine.config` for the injected `GameConfig` type —
  configuration, not game logic.

Both must stay true. The wiring introduces a NEW `src/agent/` package that sits
*above* both; nothing beneath it gains an import. **Zero edits to `src/engine/` are
required by this plan**, which is the strongest available form of non-coupling.

This should be enforced mechanically, not by reviewer memory: a test that walks the
imports of every module under `src/engine/` and fails if any names `strategy` or
`agent`. Cheap, and it converts an architectural intention into a check.

## Part A — the agent layer

A policy object per peer, constructed with an injected `GameConfig`,
`StrategySettings`, and the three strategy objects. It exposes roughly: observe the
outcome of a resolved turn, choose the next move, and learn from the transition.
Exact surface belongs in the PRD; the constraints below are the substance.

### What the policy needs, and where each piece comes from

| Input | Source | Note |
|---|---|---|
| own position | `get_observation` / `episode.cop_state.position` | always available |
| opponent position | resolved-turn payload only | **lagging** — see below |
| barrier cells | scan the grid with `Board.is_barrier` | `Board._barriers` is private; scanning 49 cells avoids an engine edit |
| turn number | `MatchState.turn_count` / `episode.turn_count` | authoritative; never caller-supplied |

`Board` has no public barrier iterator. Scanning `grid_size²` cells through
`is_barrier` is 49 calls on a 7×7 board — negligible, and it keeps Phase 1 untouched.
Adding an accessor would be the cleaner API but is not worth reopening a settled
module for.

### Per-module wiring

**pheromones** — after each resolved turn, deposit one kernel at the opponent's
revealed position and advance the field. `advance(deposits=[cell])` performs decay
and deposit in a single step, which is exactly the FR7 recurrence; calling decay and
deposit separately would double-apply the clamp and is not the intended usage.

**qvalues** — build the state key from own position, opponent position, and the
barrier set; select an action via `select_action` with the peer's injected RNG;
update on each transition. Terminal transitions use the FR6 terminal reward with
`terminal=True`.

**belief** — record `(intent, move)` for the opponent each time a reveal is
observed. This only happens in live play (see Part B limits).

### The decision that cannot be deferred

`relative_opponent` has two possible sources and they are **not**
interchangeable:

1. the opponent's position from the last resolved turn — authentic but lagging;
2. `pheromones.strongest()` — an estimate, richer but conflating observation with
   belief.

This must be decided **before any table is trained**, because `qvalues` freezes the
state layout under `STATE_LAYOUT_VERSION`. Switching sources later invalidates every
stored value and requires a version bump, discarding the series' learning.
Recommendation: source (1), because a Q-table trained on belief-derived state learns
partly about our own pheromone parameters rather than about the opponent.

## Part B — offline batch trainer

`run_tournament.py` drives `GameEpisode` **directly**, synchronously, in-process.

### Why it must NOT route through the MCP transport

`MatchState`'s buffering, its `asyncio.Lock`, and its wall-clock timeouts exist for
one purpose: reconciling two *independent, asynchronous, external* clients that may
submit in any order or not at all. In training both policies are in-process and
synchronous, so:

- the 2-slot buffer has nothing to reconcile — the trainer already holds both moves;
- `response_timeout_sec` is meaningless when no peer can be slow;
- the lock serialises calls that were never concurrent;
- stdio would serialise and re-parse JSON for thousands of turns, for nothing.

Routing training through the live protocol would therefore add latency and failure
modes while testing none of the properties that protocol exists to guarantee. The
trainer calls `episode.step(cop_token, thief_token)` and gets a `TurnResult`.

### Shape

Per game: `episode.reset()`, then loop until `is_terminated` — each policy chooses
an action from its own state, `step` resolves both, each policy learns from its own
transition. On termination, apply the FR6 terminal reward with `terminal=True`.
Repeat for `num_games`, then save each table to its own `qtable_path`.

Reproducibility is a requirement, not a nicety: a seeded RNG per role, with the seed
recorded in the run output, so a training run can be repeated and a resulting table
defended. Both `qvalues.select_action` and the trainer must take injected RNGs; the
global `random` module must not appear.

Outputs: `data/q_table_police.json`, `data/q_table_thief.json`, and a per-game score
summary. `run_tournament.py` stays at or under 150 lines; if it does not, the
episode loop belongs in its own module.

### What training does and does not exercise — stated plainly

Exercised: the Q-learning update, reward selection, pheromone decay and deposit,
state-key construction, and table persistence.

**Not** exercised:

- **`belief.py`.** There is no adversarial opponent producing intent strings, so no
  honesty evidence accumulates. Belief data comes only from real matches. A trainer
  that synthesised intents would be measuring our own generator.
- **commit-reveal, signatures, and the two-phase ordering.** Legitimately skipped —
  both policies are in-process and there is no front-running risk — but it means the
  protocol path still needs the 7b integration tests. Training passing says nothing
  about the protocol being correct.

A `q_table` produced here is therefore evidence that learning ran, not evidence that
the peer plays correctly over the wire.

## Conductor rulings — ACCEPTED

- **Sparse terminal rewards only.** Distance shaping is rejected; the reward
  structure defined in FR6 is not altered.
- **Honesty baseline.** The cop states its actual intended direction; the thief
  states the opposite of its actual move. Deterministic, no randomness.
- **Hint cap enforced by truncation** in the agent, before the intent is packed into
  the commit — so the digest covers the truncated text, not the original.
- **`config/game.json` stays untouched** at `num_games: 1`, preserving the shared
  Step-0 contract.

## Resolutions to D1–D4 — APPROVED

- **D1**: `QValues` gains `decay_epsilon()` and a MUTABLE `_epsilon` seeded from
  `settings.exploration_rate`; `select_action` reads the mutable value. New private
  `[strategy]` keys `epsilon_decay_factor` and `epsilon_floor`. The trainer calls
  `decay_epsilon()` after each game.
- **D2**: implement the hybrid SHAPE — resolved position if one exists, else
  `pheromones.strongest()`, else `None`. Understood to be behaviourally equivalent to
  the authentic source today, and correct if a vision radius is ever added.
- **D3**: `num_games` and `hint_max_words` go in the private `[strategy]` block of
  `config/<role>/game.toml`. `config/game.json` stays untouched.
- **D4**: deception is an involution with `STAY ↔ STAY`. A thief that stays tells the
  truth on that turn; the hole is accepted and documented.

## Discrepancies between the rulings and this codebase — VERIFIED (resolved above)

Each was checked against the tree, not assumed.

### D1 — there is no `q_agent.py` and no `decay_epsilon()`

The RL module is `src/strategy/qvalues.py`, class `QValues`. Its nine methods are
`state_key`, `q_value`, `update`, `reward`, `best_action`, `select_action`, `save`,
`load`, plus the constructor. Nothing decays exploration, and no file named
`q_agent.py` exists anywhere in the repository.

Consequence, which is not cosmetic: `StrategySettings` is a **frozen** dataclass and
`QValues.select_action` reads `self.settings.exploration_rate` directly. Decay
therefore requires `QValues` to hold its own MUTABLE epsilon, seeded from config on
construction, plus configured decay parameters (a factor and a floor). That is a new
method and a new piece of instance state on a module that is already committed and
tested — an additive change, but a real one, not a call to something existing.

### D2 — there is no fog-of-war trigger for the hybrid position source

`observations.build_observation` returns no opponent data at all (PRD_02 FR3), and
`observations.build_move_resolved` returns BOTH positions on every resolved turn
(PRD_02 FR4). There is no vision radius, sight range, or visibility concept anywhere
in `src/engine/` or `src/mcp_server/`.

So "use the resolved position if the opponent is currently visible, else fall back to
`pheromones.strongest()`" has no condition that can ever be false after turn 1: the
opponent's position is always known as of the last resolved turn, and never known
mid-turn. The pheromone branch would fire only at turn 0, when the field is empty and
`strongest()` returns `None`.

The hybrid's STRUCTURE is still worth implementing — resolved position when one
exists, else `pheromones.strongest()`, else `None` — because it degrades gracefully
and is the right shape if a vision radius is ever added. But it must be understood
that today it is behaviourally equivalent to the authentic-position source. Making
the fallback genuinely reachable requires either a staleness threshold (meaningless
while observations are always exactly one turn old) or an actual vision radius, which
would be a Phase 1 engine change AND a protocol change to what a resolved turn
reveals.

### D3 — `num_games` and `hint_max_words` cannot be "overridden in-memory"

Neither is a `GameConfig` field; `load_config` never reads `network_and_league.num_games`
or `world.hint_max_words`. There is no in-memory value to override.

Proposed resolution, which satisfies the intent without touching the shared contract:
put both in the peer's PRIVATE `[strategy]` block in `config/<role>/game.toml`. That
file exists precisely for private local settings, it is already loaded by
`StrategySettings`, and it keeps `game.json` — and therefore the Step-0 declaration —
untouched. It also avoids `6` and `15` appearing as literals in Python, which the
no-hardcoded-hyperparameters rule forbids.

### D4 — the opposite of `STAY` is undefined

`move_set` is `["N", "S", "E", "W", "STAY"]`. `N↔S` and `E↔W` are unambiguous;
`STAY` has no opposite, and the deception mapping must be total and deterministic.

Proposed resolution: treat the mapping as an involution with `STAY↔STAY`. It is the
only total, deterministic option. The consequence must be stated plainly: **a thief
that plays `STAY` states `STAY` and is therefore honest on that turn**, so the
deception has a hole the belief engine will score as honest.

### Strategic note on the deception baseline

A 100% deterministically deceptive thief is perfectly predictable. Our own
`belief.py` will drive its honesty rate to 0, at which point inverting the stated
intent recovers the true move exactly. Maximal deception leaks as much information as
maximal honesty; only a mixed strategy conceals anything. This is acceptable as the
deterministic BASELINE it was specified to be, but it should not be mistaken for a
strong strategy, and a future phase may want a randomised deception rate.

## Open items needing a decision

1. **Credit assignment is weak.** With no intermediate reward, γ=0.9 and up to 35
   moves, the terminal signal reaching the first move is 0.9³⁵ ≈ 0.025. Over a
   6-game series, early-game play will barely move. Options: accept it, or add
   distance-based shaping — which needs new configured weights and changes what the
   agent optimises. Not silently added.
2. **No exploration schedule.** `exploration_rate` is a fixed config value, so the
   agent explores just as much in game 6 as in game 1, which costs points in a
   scored series. A decay schedule would need its own configured parameters.
3. **Is our agent honest?** The policy must emit an `intent` when committing.
   Always stating the true direction is honest and legible; deliberately misstating
   it is a legitimate strategy that our own `belief.py` is designed to detect in an
   opponent. Nothing in any document decides this, and it is a game-theoretic
   choice, not an implementation detail.
4. **`hint_max_words: 15` is unenforced.** It is not exposed by `GameConfig`, and
   FR9 deliberately excluded intent length from honesty scoring. If the cap is a
   protocol rule, it belongs at the tool surface in 7b, with a third additive config
   extension.
5. **Series length.** `num_games` is still 1 in the shared `game.json` while the
   guidelines mandate 6. Training against 1 produces a materially weaker table, and
   the value also flows into the Step-0 declaration. Already deferred into the 7b
   interop conversation; recorded here because it directly bounds training value.

## Approval gate

No implementation until this is promoted into `PRD_05`, the `relative_opponent`
source is chosen, and items 1–3 above are decided. Part A additionally waits on 7b.
