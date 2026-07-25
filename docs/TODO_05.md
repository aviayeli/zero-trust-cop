# TODO — Phase 5: Wiring and Training

From the approved `PLAN_05_Wiring_and_Training.md`, including the D1–D4 resolutions.
Strict TDD throughout: a failing test precedes every implementation change, and each
step is its own commit. Every Python file at or under 150 lines — tests included.

Steps 1–3 are a dependency chain. Step 4 is the training run that produces the
deliverables. Step 5 is a guard that should land before the agent grows.

## 1. Exploration decay on `QValues` (D1) + the four new private settings

- [ ] Test first: `epsilon` starts at `settings.exploration_rate`; `decay_epsilon()`
      multiplies it by `epsilon_decay_factor`; it never falls below `epsilon_floor`;
      repeated calls clamp at the floor rather than approaching zero.
- [ ] Test that `select_action` honours the DECAYED value, not the frozen config one —
      with the floor at 0.0 and one decay to 0.0, selection must be provably greedy.
- [ ] Test the four new `[strategy]` keys load and are typed: `epsilon_decay_factor`
      (float), `epsilon_floor` (float), `num_games` (int), `hint_max_words` (int).
      A missing key must still raise KeyError — no defaults.
- [ ] Confirm RED, then implement: mutable `_epsilon` on `QValues`, `decay_epsilon()`,
      four fields on `StrategySettings`, four keys in BOTH `config/<role>/game.toml`.
- [ ] `StrategySettings` stays frozen; the mutable epsilon lives on `QValues`, not on
      the settings object.
- [ ] Confirm GREEN; confirm `qtable_path` values still differ between the two roles.
- [ ] Confirm every touched file is at or under 150 lines.

## 2. `src/agent/agent_core.py` — the policy layer

- [ ] Test first, with injected `GameConfig`, `StrategySettings`, `QValues`,
      `PheromoneField` and `BeliefTracker`:
  - [ ] The state source is the hybrid (D2): resolved position when one exists, else
        `pheromones.strongest()`, else `None`. Assert all three branches.
  - [ ] Barriers are collected by scanning `Board.is_barrier`; no engine change.
  - [ ] The COP's intent states its actual move direction (honest).
  - [ ] The THIEF's intent states the OPPOSITE of its actual move, with `STAY`
        mapping to `STAY` (D4) — assert the STAY case explicitly, since it is the
        documented hole.
  - [ ] Intent is truncated to `hint_max_words` BEFORE it is returned, so a commit
        digest covers the truncated text. Assert a >15-word intent is cut.
  - [ ] The policy records the opponent's revealed `(intent, move)` into
        `BeliefTracker`, and deposits the opponent's revealed position into the
        pheromone field via a single `advance(deposits=[cell])` call.
  - [ ] The policy performs one `QValues.update` per transition, with `terminal=True`
        only on the final turn.
- [ ] Confirm RED, then implement. `src/agent/` must import from `strategy` and read
      engine STATE, but must not be imported BY anything under `src/engine/`.
- [ ] Confirm GREEN; file at or under 150 lines (split if it approaches the limit).

## 3. `src/scripts/run_tournament.py` — offline batch trainer

- [ ] Test first:
  - [ ] It drives `GameEpisode.step` DIRECTLY. Assert no import of
        `mcp_server.match_state`, `mcp_server.server`, or any MCP transport — the
        buffering exists to reconcile independent async clients and is pure overhead
        here (PLAN_05 Part B).
  - [ ] `num_games` comes from the private `[strategy]` block, NOT from
        `config/game.json`, which stays at 1 (D3).
  - [ ] A seeded run is reproducible: two runs with the same seed produce identical
        tables and identical per-game scores.
  - [ ] `decay_epsilon()` is called once per completed game.
  - [ ] Each role's table is written to its own `qtable_path`; the two paths differ.
  - [ ] Tests write ONLY under `tmp_path` — no `data/` artifact from a test run.
- [ ] Confirm RED, then implement. No global `random`; injected RNG per role.
- [ ] Confirm GREEN; file at or under 150 lines — extract the episode loop if not.

## 4. Execute the real training run and commit the deliverables

- [ ] Run the trainer for real, over `num_games` games, recording the seed.
- [ ] Verify the outputs are genuine: both tables non-empty, `state_layout_version`
      present, and the values differ from a freshly initialised table.
- [ ] Confirm `data/q_table_police.json` and `data/q_table_thief.json` are TRACKED,
      not ignored.
- [ ] Commit them as deliverables, recording the seed and the resulting scores in the
      commit message so the artifact is reproducible and defensible.

## 5. Import-direction guard

- [ ] Test that walks every module under `src/engine/` and fails if any imports from
      `strategy` or `agent`. Converts the architectural intention in PLAN_05 into a
      check that cannot decay.
- [ ] Confirm it passes today (it should — verified manually while planning).

## Out of scope for Phase 5

- Wiring the policy into the live tool surface. That needs Step 7b, which is blocked
  on the opposing group agreeing to the FR7 schemas.
- Any change to `config/game.json`, including `num_games`.
- A vision radius (see D2) — engine and protocol change, its own phase.
- Randomised deception. The 100% deterministic thief is a baseline, and PLAN_05
  records why it is weak.
