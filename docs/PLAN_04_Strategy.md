# PLAN — Phase 4: Strategic Engine

## Status

DRAFT, from the approved `PRD_04_Strategy.md`. The two ambiguities PRD_04 deferred
are resolved below with the Conductor's definitions. FR1 is the only step
dispatchable immediately; everything else depends on it.

## Design Principles Applied

- **Simplicity first**: stdlib only, no numpy. A dict-backed table and a dict of
  cell concentrations are sufficient at 7×7.
- **Surgical changes**: FR1 is additive to `GameConfig`; nothing existing changes.
- **Goal-driven**: every module traces to an FR in PRD_04.

## Module Architecture — the 3-way split is mandatory

```
src/engine/config.py        (edit, FR1)  expose the pheromones block
config/<role>/game.toml     (new,  FR2)  private [strategy] hyperparameters
src/strategy/__init__.py    (new)        package marker
src/strategy/pheromones.py  (new,  FR7)  5×5 kernels, decay, global fusion
src/strategy/qvalues.py     (new,  FR4-FR6, FR8)  state key, update, persistence
src/strategy/belief.py      (new,  FR9)  intent-vs-move honesty
```

Three subsystems in one file would breach 150 lines on arrival. Each module is
also independently testable, which the pheromone recurrence in particular needs.

## RESOLVED — FR7: what `pheromone_grid_size: 5` means

It is the **side length of the opponent's smell footprint**, not a coarser overlay
and not the board size (the board is `grid_size: 7`).

Model:

1. Each observation of an opponent trace deposits a **5×5 kernel centred on the
   observed cell**, with `pheromone_center_intensity` (0.9) at the centre.
2. Every cell decays each tick by the exact recurrence, ρ = `pheromone_decay` (0.1):

       τij(t+1) = max(0, (1-ρ) * τij(t) + Δτij)

3. Individual 5×5 footprints are **fused globally** into one belief heatmap over
   the 7×7 board, by summing overlapping contributions.

Implementation constraints:

- Decay applies to EVERY cell each tick; deposit only where a trace was observed.
- A 5×5 kernel centred near an edge is **clipped** to the board — deposits must
  never write outside `grid_size`, and clipping must not silently wrap.
- `max(0, ...)` is enforced per cell after every update, so no concentration can
  go negative even if Δτ is negative. This is a hard invariant, not a formality.
- Kernel side length, centre intensity and ρ all come from config (FR1). The
  falloff from centre to kernel edge must be documented in the module docstring,
  since the chapter fixes the centre value but not the profile.

## RESOLVED — FR4: the Q-table state key

    state = (relative_opponent, barrier_mask)

- `relative_opponent`: `(Δrow, Δcol)` from the acting agent to the opponent, or
  `None` when the opponent has not been observed (fog of war).
- `barrier_mask`: a 4-bit integer, one bit per immediately adjacent cell in a
  fixed UP/DOWN/LEFT/RIGHT order, set when that neighbour holds a barrier.
- `move_count` is **excluded** deliberately: including it would multiply the state
  space by 35 and make almost every state unique, so nothing would ever be revisited
  and the table could not generalise.

Where `relative_opponent` comes from — this is load-bearing and easy to get wrong:

- NOT from `get_observation`, which excludes the opponent's position (PRD_02 FR3).
- From the resolved-turn payload, `observations.build_move_resolved`, which returns
  both `cop_position` and `thief_position` (PRD_02 FR4).

So the value is a **lagging** observation: the opponent's position as of the last
resolved turn, never the current one. `None` applies before the first resolution.
The module must not pretend this is live information.

State space size: 4 bits of barriers × (relative offsets over a 7×7 board, plus
`None`) — small enough that a 6-game series revisits states, which is the whole
reason for excluding `move_count`.

## FR2 — private hyperparameters

`config/<role>/game.toml`, read with `tomllib` (stdlib):

```toml
[strategy]
learning_rate = 0.1
discount_factor = 0.9
exploration_rate = 0.1
initial_q_value = 0.0
qtable_path = "config/police/qtable.json"
invalid_move_penalty = -1.0
```

Values above are illustrative; the file is the source of truth and no strategy
module may fall back to a literal. Missing keys fail loudly — the Phase 3 FR1
lesson: a config that loads with silent defaults is worse than one that raises.

`game.json` is untouched and continues to serve the engine.

## FR5/FR6 — update rule and rewards

    Q(s,a) <- Q(s,a) + α * ( r + γ * max_a' Q(s',a') - Q(s,a) )

- α, γ from `[strategy]`. Unseen `(s,a)` returns `initial_q_value`, never raises.
- Terminal rewards from `config/game.json` → `scoring`, selected by role and
  outcome: `capture_cop` 20, `capture_thief` 5, `survival_cop` 5,
  `survival_thief` 10, `tie_score` 2, `technical_loss` 0.
- Shaping penalty for a move into a barrier or off-board, from `[strategy]`.
- Action space from `movement_and_barriers.move_set`, never a literal list.

## FR8 — persistence and layout guarding

The table persists as JSON at `qtable_path`. Tuple keys are not JSON-native, so
the encoding must be explicit and reversible, and documented.

The file records a **state-layout version**. Loading a table whose layout does not
match the running code must RAISE, not merge. Silently mixing values keyed by a
different feature tuple would corrupt learning invisibly — the same class of
failure as Phase 3's wrong-algorithm key that loaded successfully.

## FR9 — intent-vs-move consistency

Per opponent, record each revealed `(intent, move)` and whether the intent's stated
direction matched the move actually played.

- Direction matching: case-insensitive search for direction tokens — full words
  (`north`, `south`, `east`, `west`, `stay`) and the single letters from
  `move_set` (`N`, `S`, `E`, `W`) as standalone words, so "SNOW" does not read as
  `N`. The matcher belongs in `belief.py` and must be tested on adversarial text.
- Intent naming **no** direction is UNSCORABLE: not honest, not dishonest.
  Counting silence as a lie would poison the rate.
- Intent naming a direction that contradicts the move counts as dishonest.
- Honesty rate starts from a configurable prior so a peer with no history is
  neither trusted nor condemned.
- `world.hint_max_words: 15` bounds intent length; longer intent is a protocol
  concern, not a lie, and must not be scored as dishonesty.

The evidence is authentic because commit-reveal binds `intent` to its move — an
opponent cannot retroactively change what it claimed. That is what makes this
measurable rather than guesswork.

## Ordering

1. **FR1** — additive `GameConfig` extension for the pheromones block. Blocks all
   pheromone work; dispatchable now; no strategy module yet.
2. **FR2** — `config/<role>/game.toml` plus its loader.
3. **FR7** — `pheromones.py`. Independent of the Q-table.
4. **FR4/FR5/FR6/FR8** — `qvalues.py`. Depends on FR2.
5. **FR9** — `belief.py`. Independent of the other two.
6. Wiring into the tool surface is OUT OF SCOPE until Step 7b lands.

Steps 3, 4 and 5 are mutually independent once FR1 and FR2 exist, and each is its
own commit.

## Open Items

- `num_games` is 1 in `config/game.json` but the guidelines mandate 6, and the
  value flows into the Step-0 declaration. Needs an explicit decision — it changes
  the shared `agreed_between` contract and the published artifact.
- The pheromone kernel falloff profile: the chapter fixes the centre intensity but
  not how it decreases toward the kernel edge. To be recorded in TODO_04 before
  FR7 is implemented.

## Approval Gate

FR1 may be dispatched on approval of this plan. FR7 additionally requires the
falloff profile decided.
